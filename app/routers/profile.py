from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates
from app.database import supabase
from app.minio_handler import minio_client

router = APIRouter(tags=["User Profile"])
templates = Jinja2Templates(directory="templates")

@router.get("/userProfile")
def get_profile_page(request: Request):
    access_token = request.cookies.get("access_token")
    if not access_token:
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url="/login")

    try:
        user_response = supabase.auth.get_user(access_token)
        user = user_response.user
        
        profile = supabase.table("Profiles").select("*").eq("id", user.id).single().execute()
        
        # Fetch reports count
        reports_res = supabase.table("Reports").select("*", count="exact").eq("user_id", user.id).execute()
        reports_count = reports_res.count if reports_res.count is not None else 0

        # Fetch recent chats for preview (last 6 messages to show some context)
        # Using correct table name: Chat_History
        chats_res = supabase.table("Chat_History").select("*").eq("user_id", user.id).order("created_at", desc=True).limit(6).execute()
        recent_chats = chats_res.data[::-1] if chats_res.data else [] 

        # Fetch User_Features safely
        user_features = None
        try:
            features_res = supabase.table("User_Features").select("*").eq("user_id", user.id).maybe_single().execute()
            user_features = features_res.data if features_res.data else None
        except Exception as f_err:
            print(f"User features fetch error: {f_err}")

        return templates.TemplateResponse("userprofile.html", {
            "request": request,
            "user_name": profile.data.get("full_name", "User"),
            "user_email": user.email,
            "grade_level": profile.data.get("grade_level", "Not set"),
            "gender": profile.data.get("gender", "Not set"),
            "reports_count": reports_count,
            "recent_chats": recent_chats,
            "user_features": user_features
        })
    except Exception as e:
        print(f"Profile Dashboard Error: {e}")
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url="/login")




        
@router.get("/settings")
async def get_settings_page(request: Request):
    access_token = request.cookies.get("access_token")
    if not access_token:
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url="/login")

    try:
        user_response = supabase.auth.get_user(access_token)
        user = user_response.user
        
        # Fetch profile data to pass to the settings page
        profile = supabase.table("Profiles").select("*").eq("id", user.id).single().execute()
        
        # Fetch avatars from MinIO
        minio_images = minio_client.get_all_images()
        
        return templates.TemplateResponse("settings.html", {
            "request": request,
            "minio_avatars": minio_images,
            "user_name": profile.data.get("full_name", "User"),
            "user_email": user.email,
            "grade_level": profile.data.get("grade_level", ""),
            "gender": profile.data.get("gender", ""),
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
    except Exception:
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url="/login")




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
