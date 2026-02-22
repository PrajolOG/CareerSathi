from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates
from app.database import supabase

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
        
        return templates.TemplateResponse("userprofile.html", {
            "request": request,
            "user_name": profile.data.get("full_name", "User"),
            "user_email": user.email,
            "grade_level": profile.data.get("grade_level", "Not set"),
            "gender": profile.data.get("gender", "Not set")
        })
    except Exception:
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url="/login")
