import re
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Request, HTTPException, UploadFile, File, Form
from fastapi.templating import Jinja2Templates
from starlette.concurrency import run_in_threadpool
from app.schemas import ChatMessage
from app.services.chat_service import ChatService
from app.database import supabase, url, key
from supabase import create_client, ClientOptions
from app.minio_handler import minio_client
from app.services.ocr_service import ocr_service
from app.chat_upload_meta import build_upload_message

router = APIRouter(tags=["Chat System"])
templates = Jinja2Templates(directory="templates")

# Initialize Services
chat_service = ChatService()


def _safe_bucket_name(full_name: str, user_id: str) -> str:
    base = re.sub(r"[^a-z0-9-]+", "-", (full_name or "user").lower()).strip("-")
    base = re.sub(r"-{2,}", "-", base)
    if not base:
        base = "user"

    short_id = re.sub(r"[^a-z0-9]", "", (user_id or "").lower())[:8] or "anon0000"
    max_base_len = max(3, 63 - len(short_id) - 1)
    base = base[:max_base_len].strip("-") or "user"

    bucket_name = f"{base}-{short_id}"
    bucket_name = bucket_name[:63].strip("-")
    if len(bucket_name) < 3:
        bucket_name = f"user-{short_id}"
    return bucket_name


def _safe_object_name(original_name: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", Path(original_name or "upload.png").name)
    if not cleaned:
        cleaned = "upload.png"
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    return f"{stamp}-{cleaned}"

@router.get("/chat")
def get_chat_page(request: Request):
    # 1. Check Cookie
    access_token = request.cookies.get("access_token")
    if not access_token:
        raise HTTPException(status_code=401, detail="Unauthorized")

    try:
        # 2. Validate User
        user_response = supabase.auth.get_user(access_token)
        user = user_response.user
    except Exception as e:
        print(f"Authentication failed: {e}")
        raise HTTPException(status_code=401, detail="Unauthorized") from e

    try:
        # 3. Create Scoped Client for Data Fetching
        client = create_client(
            url, 
            key, 
            options=ClientOptions(headers={"Authorization": f"Bearer {access_token}"})
        )

        # 4. Fetch Profile
        profile = client.table("Profiles").select("*").eq("id", user.id).single().execute()
        
        # 5. Fetch History (Increased limit for full sync)
        history_response = client.table("Chat_History")\
            .select("*")\
            .eq("user_id", user.id)\
            .order("created_at", desc=False)\
            .limit(200)\
            .execute()
            
        chat_history = history_response.data if history_response.data else []
        
        return templates.TemplateResponse("chat.html", {
            "request": request,
            "user_name": profile.data.get("full_name", "User"),
            "user_email": user.email,
            "user_profile_pic": profile.data.get("profile_url"),
            "chat_history": chat_history
        })

    except Exception as e:
        print(f"Error loading chat page data: {e}")
        # If data fetching fails, we can still show the page but maybe with an error or empty state
        # DO NOT redirect to login as the user is authenticated
        return templates.TemplateResponse("chat.html", {
            "request": request,
            "user_name": "User",
            "chat_history": [],
            "error_message": "Failed to load chat history. Please refresh."
        })


@router.post("/chat")
async def chat_with_bot(request: Request, chat_data: ChatMessage):
    access_token = request.cookies.get("access_token")
    if not access_token:
        return {"bot_response": "Authentication failed. Please log in again."}

    async def event_generator():
        try:
            async for chunk in chat_service.stream_career_advice(chat_data.message, access_token):
                yield chunk
        except Exception as e:
            print(f"Streaming Error: {e}")
            yield "Sorry, a system error occurred."

    from fastapi.responses import StreamingResponse
    return StreamingResponse(event_generator(), media_type="text/plain")


@router.post("/chat/image")
async def chat_with_document(
    request: Request,
    image: UploadFile = File(...),
    message: str = Form(""),
):
    access_token = request.cookies.get("access_token")
    if not access_token:
        return {"bot_response": "Authentication failed. Please log in again."}

    content_type = (image.content_type or "").lower()
    file_name = image.filename or "upload"
    is_pdf = content_type == "application/pdf" or file_name.lower().endswith(".pdf")
    is_image = content_type.startswith("image/")

    if not is_image and not is_pdf:
        return {"bot_response": "Please upload a valid image or PDF file."}

    default_file_name = "upload.pdf" if is_pdf else "upload.png"

    file_bytes = await image.read()
    if not file_bytes:
        return {"bot_response": "Uploaded file is empty. Please try again."}

    try:
        user_response = supabase.auth.get_user(access_token)
        user = user_response.user

        scoped_client = create_client(
            url,
            key,
            options=ClientOptions(headers={"Authorization": f"Bearer {access_token}"})
        )
        profile_res = scoped_client.table("Profiles").select("full_name").eq("id", user.id).single().execute()
        full_name = profile_res.data.get("full_name", "User") if profile_res and profile_res.data else "User"
    except Exception as auth_error:
        print(f"Auth/Profile fetch failed for document chat: {auth_error}")
        return {"bot_response": "Authentication failed. Please log in again."}

    bucket_name = _safe_bucket_name(full_name, user.id)
    object_name = _safe_object_name(image.filename or default_file_name)

    bucket_ok, bucket_msg = minio_client.ensure_bucket(bucket_name)
    if not bucket_ok:
        print(f"MinIO bucket ensure failed: {bucket_msg}")
        return {"bot_response": "Could not prepare storage for your upload. Please try again."}

    upload_ok, upload_msg = minio_client.upload_file(
        bucket_name=bucket_name,
        object_name=object_name,
        file_data=file_bytes,
        content_type=image.content_type or "application/octet-stream",
    )
    if not upload_ok:
        print(f"MinIO upload failed: {upload_msg}")
        return {"bot_response": "Could not upload your file. Please try again."}

    if is_pdf:
        ocr_text = await run_in_threadpool(ocr_service.extract_text_from_pdf_bytes, file_bytes)
    else:
        ocr_text = await run_in_threadpool(ocr_service.extract_text_from_image_bytes, file_bytes)

    if not ocr_text:
        ocr_text = (
            "OCR could not confidently read text from this file. "
            "Please ask for missing values and request a clearer image or PDF if needed."
        )

    clean_message = (message or "").strip()
    user_message_for_db = build_upload_message(
        user_text=clean_message,
        file_name=image.filename or default_file_name,
        object_name=object_name,
        bucket_name=bucket_name,
        file_type="pdf" if is_pdf else "image",
    )

    async def event_generator():
        try:
            async for chunk in chat_service.stream_career_advice(
                user_message=clean_message,
                user_token=access_token,
                ocr_text=ocr_text,
                user_message_for_db=user_message_for_db,
            ):
                yield chunk
        except Exception as e:
            print(f"Document Streaming Error: {e}")
            yield "Sorry, a system error occurred while processing your file."

    from fastapi.responses import StreamingResponse
    return StreamingResponse(event_generator(), media_type="text/plain")


@router.delete("/chat/history")
async def reset_chat_history(request: Request):
    access_token = request.cookies.get("access_token")
    if not access_token:
        raise HTTPException(status_code=401, detail="Authentication failed.")

    try:
        user_response = supabase.auth.get_user(access_token)
        user = user_response.user
        
        # We need a scoped client to delete history
        client = create_client(
            url, 
            key, 
            options=ClientOptions(headers={"Authorization": f"Bearer {access_token}"})
        )
        
        # Hard delete user's chat history
        delete_res = client.table("Chat_History").delete().eq("user_id", user.id).execute()
        
        return {"status": "success", "message": "Chat history deleted."}
    except Exception as e:
        print(f"Error deleting chat history: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete chat history.")
