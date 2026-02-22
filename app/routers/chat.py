import os
from fastapi import APIRouter, Request, HTTPException
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse
from app.schemas import ChatMessage
from app.services.chat_service import ChatService
from app.services.speech import SpeechService
from app.database import supabase, url, key
from supabase import create_client, ClientOptions

router = APIRouter(tags=["Chat System"])
templates = Jinja2Templates(directory="templates")

# Initialize Services
chat_service = ChatService()

@router.get("/chat")
def get_chat_page(request: Request):
    # 1. Check Cookie
    access_token = request.cookies.get("access_token")
    if not access_token:
        return RedirectResponse(url="/login")

    try:
        # 2. Validate User
        user_response = supabase.auth.get_user(access_token)
        user = user_response.user
        
        # 3. Create Scoped Client for Data Fetching
        # We need this to get Profile/History via RLS
        client = create_client(
            url, 
            key, 
            options=ClientOptions(headers={"Authorization": f"Bearer {access_token}"})
        )

        # 4. Fetch Profile
        profile = client.table("Profiles").select("*").eq("id", user.id).single().execute()
        
        # 5. Fetch History
        history_response = client.table("Chat_History")\
            .select("*")\
            .eq("user_id", user.id)\
            .order("created_at", desc=False)\
            .limit(50)\
            .execute()
            
        chat_history = history_response.data if history_response.data else []
        
        return templates.TemplateResponse("chat.html", {
            "request": request,
            "user_name": profile.data.get("full_name", "User"),
            "user_email": user.email,
            "chat_history": chat_history
        })

    except Exception as e:
        print(f"Error loading chat page: {e}")
        # If anything fails (token expired, db error), kick to login
        return RedirectResponse(url="/login")


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


@router.post("/speech")
async def generate_speech(request: Request, payload: dict):
    try:
        text = payload.get("text")
        if not text:
            raise HTTPException(status_code=400, detail="Text is required")

        # CHANGE IS HERE: Added 'await' because EdgeTTS is async
        audio_stream = await speech_service.generate_audio(text)
        
        from fastapi.responses import StreamingResponse
        return StreamingResponse(audio_stream, media_type="audio/mpeg")
    except Exception as e:
        # print(f"Speech Gen Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))