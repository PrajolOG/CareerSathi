import re
from datetime import timedelta, timezone

from fastapi import APIRouter, Request, Form, HTTPException
from fastapi.templating import Jinja2Templates
from app.database import supabase
from app.minio_handler import minio_client
from app.chat_upload_meta import parse_upload_message

router = APIRouter(tags=["User Profile"])
templates = Jinja2Templates(directory="templates")


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

@router.get("/userProfile")
def get_profile_page(request: Request):
    access_token = request.cookies.get("access_token")
    if not access_token:
        raise HTTPException(status_code=401, detail="Unauthorized")

    try:
        user_response = supabase.auth.get_user(access_token)
        user = user_response.user
        
        profile = supabase.table("Profiles").select("*").eq("id", user.id).single().execute()
        
        # Fetch reports count
        reports_res = supabase.table("Reports").select("*", count="exact").eq("user_id", user.id).execute()
        reports_count = reports_res.count if reports_res.count is not None else 0

        # Fetch recent chats for preview (last 6 messages to show some context)
        # Using correct table name: Chat_History
        chats_res = supabase.table("Chat_History").select("*").eq("user_id", user.id).order("created_at", desc=True).limit(12).execute()
        recent_chats = chats_res.data[::-1] if chats_res.data else [] 
        for chat in recent_chats:
            if chat.get("sender") == "user":
                meta, clean_text = parse_upload_message(chat.get("message", ""))
                if meta is not None:
                    fallback_name = meta.get("file_name", "image")
                    chat["message"] = clean_text or f"Uploaded image: {fallback_name}"

        # Fetch User_Features safely
        user_features = None
        try:
            features_res = supabase.table("User_Features").select("*").eq("user_id", user.id).maybe_single().execute()
            user_features = features_res.data if features_res.data else None
        except Exception as f_err:
            print(f"User features fetch error: {f_err}")

        # Fetch resources from MinIO
        resources = []
        user_name = profile.data.get("full_name", "User")
        try:
            bucket_name = _safe_bucket_name(user_name, user.id)
            objects = minio_client.list_bucket_objects(bucket_name)
            nepal_tz = timezone(timedelta(hours=5, minutes=45))
            
            for obj in objects:
                last_modified = obj.get("last_modified")
                formatted_last_modified = "Unknown"
                if last_modified:
                    try:
                        formatted_last_modified = last_modified.astimezone(nepal_tz).strftime("%Y-%m-%d %I:%M %p")
                    except Exception:
                        formatted_last_modified = str(last_modified)

                resources.append({
                    "name": obj.get("name", "unnamed-file"),
                    "size": obj.get("size", "0.00 MB"),
                    "last_modified": formatted_last_modified,
                    "presigned_url": obj.get("presigned_url", ""),
                    "is_image": obj.get("is_image", False),
                })
        except Exception as r_err:
            print(f"Resources fetch error: {r_err}")

        return templates.TemplateResponse("userprofile.html", {
            "request": request,
            "user_name": user_name,
            "user_email": user.email,
            "grade_level": profile.data.get("grade_level", "Not set"),
            "gender": profile.data.get("gender", "Not set"),
            "user_profile_pic": profile.data.get("profile_url"),
            "reports_count": reports_count,
            "recent_chats": recent_chats,
            "user_features": user_features,
            "resources": resources
        })
    except Exception as e:
        print(f"Profile Dashboard Error: {e}")
        raise HTTPException(status_code=401, detail="Unauthorized") from e


@router.get("/my-stuff")
def get_my_stuff_page(request: Request):
    access_token = request.cookies.get("access_token")
    if not access_token:
        raise HTTPException(status_code=401, detail="Unauthorized")

    try:
        user_response = supabase.auth.get_user(access_token)
        user = user_response.user

        profile = supabase.table("Profiles").select("*").eq("id", user.id).single().execute()
        user_name = profile.data.get("full_name", "User")
        user_profile_pic = profile.data.get("profile_url")

        bucket_name = _safe_bucket_name(user_name, user.id)
        objects = minio_client.list_bucket_objects(bucket_name)

        nepal_tz = timezone(timedelta(hours=5, minutes=45))
        resources = []

        for obj in objects:
            last_modified = obj.get("last_modified")
            if last_modified:
                try:
                    formatted_last_modified = last_modified.astimezone(nepal_tz).strftime("%Y-%m-%d %I:%M %p")
                except Exception:
                    formatted_last_modified = str(last_modified)
            else:
                formatted_last_modified = "Unknown"

            resources.append({
                "name": obj.get("name", "unnamed-file"),
                "size": obj.get("size", "0.00 MB"),
                "last_modified": formatted_last_modified,
                "presigned_url": obj.get("presigned_url", ""),
                "is_image": obj.get("is_image", False),
            })

        return templates.TemplateResponse("my_stuff.html", {
            "request": request,
            "user_name": user_name,
            "user_profile_pic": user_profile_pic,
            "bucket_name": bucket_name,
            "resources": resources,
        })
    except Exception as e:
        print(f"My Stuff Page Error: {e}")
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url="/userProfile")


@router.get("/profile/my-stuff/json")
def get_my_stuff_json(request: Request):
    access_token = request.cookies.get("access_token")
    if not access_token:
        from fastapi.responses import JSONResponse

        return JSONResponse({"error": "Unauthorized"}, status_code=401)

    try:
        user_response = supabase.auth.get_user(access_token)
        user = user_response.user

        profile = (
            supabase.table("Profiles")
            .select("full_name")
            .eq("id", user.id)
            .single()
            .execute()
        )
        user_name = profile.data.get("full_name", "User")

        bucket_name = _safe_bucket_name(user_name, user.id)
        objects = minio_client.list_bucket_objects(bucket_name)

        nepal_tz = timezone(timedelta(hours=5, minutes=45))
        resources = []

        for obj in objects:
            last_modified = obj.get("last_modified")
            formatted_last_modified = "Unknown"
            if last_modified:
                try:
                    formatted_last_modified = last_modified.astimezone(nepal_tz).strftime(
                        "%Y-%m-%d %I:%M %p"
                    )
                except Exception:
                    formatted_last_modified = str(last_modified)

            resources.append(
                {
                    "name": obj.get("name", "unnamed-file"),
                    "size": obj.get("size", "0.00 MB"),
                    "last_modified": formatted_last_modified,
                    "presigned_url": obj.get("presigned_url", ""),
                    "is_image": obj.get("is_image", False),
                }
            )

        return {"resources": resources, "bucket_name": bucket_name}
    except Exception as e:
        print(f"My Stuff JSON Error: {e}")
        from fastapi.responses import JSONResponse

        return JSONResponse({"error": str(e)}, status_code=500)





        
@router.get("/settings")
async def get_settings_page(request: Request):
    access_token = request.cookies.get("access_token")
    if not access_token:
        raise HTTPException(status_code=401, detail="Unauthorized")

    try:
        user_response = supabase.auth.get_user(access_token)
        user = user_response.user
        
        # Fetch profile data to pass to the settings page
        profile = supabase.table("Profiles").select("*").eq("id", user.id).single().execute()
        
        minio_avatars = minio_client.get_all_images("user-icons")
        
        return templates.TemplateResponse("settings.html", {
            "request": request,
            "minio_avatars": minio_avatars,
            "user_name": profile.data.get("full_name", "User"),
            "user_email": user.email,
            "grade_level": profile.data.get("grade_level", ""),
            "gender": profile.data.get("gender", ""),
            "user_profile_pic": profile.data.get("profile_url"),
            "education_levels": [
                {"label": "High School (+2 Science)", "value": "High School (+2 Science)", "icon": "fa-flask"},
                {"label": "High School (+2 Management)", "value": "High School (+2 Management)", "icon": "fa-briefcase"},
                {"label": "A-Levels", "value": "A-Levels", "icon": "fa-scroll"},
                {"label": "Bachelors (Undergraduate)", "value": "Bachelors (Undergraduate)", "icon": "fa-university"},
                {"label": "Masters (Postgraduate)", "value": "Masters (Postgraduate)", "icon": "fa-award"}
            ],
            "genders": [
                {"label": "Male", "value": "Male", "icon": "fa-mars"},
                {"label": "Female", "value": "Female", "icon": "fa-venus"},
                {"label": "Other", "value": "Other", "icon": "fa-genderless"}
            ]
        })
    except Exception as e:
        raise HTTPException(status_code=401, detail="Unauthorized") from e




@router.post("/settings/update")
async def update_profile_settings(
    request: Request,
    full_name: str = Form(None),
    grade_level: str = Form(None),
    gender: str = Form(None),
    selected_avatar: str = Form(None)
):
    access_token = request.cookies.get("access_token")
    if not access_token:
        raise HTTPException(status_code=401, detail="Unauthorized")

    try:
        user_response = supabase.auth.get_user(access_token)
        user = user_response.user

        # Build update dictionary dynamically
        update_data = {}
        if full_name: update_data["full_name"] = full_name
        if grade_level: update_data["grade_level"] = grade_level
        if gender: update_data["gender"] = gender
        if selected_avatar: update_data["profile_url"] = selected_avatar

        if update_data:
            supabase.table("Profiles").update(update_data).eq("id", user.id).execute()

        from fastapi.responses import RedirectResponse
        return RedirectResponse(url="/settings", status_code=303)

    except Exception as e:
        print(f"Error updating profile: {e}")
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url="/settings")


@router.delete("/profile/context")
async def delete_model_context(request: Request):
    """
    Deletes the current user's entry in the User_Features table.
    """
    access_token = request.cookies.get("access_token")
    if not access_token:
        from fastapi.responses import JSONResponse
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
        
    try:
        user_response = supabase.auth.get_user(access_token)
        user = user_response.user
        
        # Delete row from User_Features for the active user
        delete_res = supabase.table("User_Features").delete().eq("user_id", user.id).execute()
        
        return {"success": True, "message": "Model context successfully reset."}
    except Exception as e:
        print(f"Error resetting model context: {e}")
        from fastapi.responses import JSONResponse
        return JSONResponse({"error": "Failed to reset model context"}, status_code=500)
