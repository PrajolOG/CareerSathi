from fastapi import APIRouter, HTTPException, Request, Form, Depends
from fastapi.templating import Jinja2Templates
from app.database import supabase
from typing import Optional

router = APIRouter(tags=["Authentication"])
templates = Jinja2Templates(directory="templates")

@router.get("/signup")
def signup_page(request: Request):
    return templates.TemplateResponse("signup.html", {"request": request})

@router.post("/signup")
def signup(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    full_name: str = Form(...),
    grade_level: str = Form(...),
    gender: str = Form(...)
):
    try:
        # 1. Sign up
        auth_response = supabase.auth.sign_up({
            "email": email,
            "password": password,
        })

        if not auth_response.user or not auth_response.user.id:
            return templates.TemplateResponse("signup.html", {"request": request, "error": "Signup failed: No user returned"})

        user_id = auth_response.user.id

        profile_data = {
            "id": user_id,
            "full_name": full_name,
            "grade_level": grade_level,
            "gender": gender
        }
        
        supabase.table("Profiles").insert(profile_data).execute()

        from fastapi.responses import RedirectResponse
        response = RedirectResponse(url="/welcome", status_code=303)
        # Set a temporary cookie to allow access to /welcome for 1 minute
        response.set_cookie(key="signup_success", value="true", max_age=60, httponly=True)
        
        # Also set the access token if session is available (email confirm disabled)
        if auth_response.session:
            response.set_cookie(key="access_token", value=auth_response.session.access_token, httponly=True, secure=True)
            
        return response

    except Exception as e:
        return templates.TemplateResponse("signup.html", {"request": request, "error": str(e)})


@router.get("/login")
def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@router.post("/login")
def login(request: Request, email: str = Form(...), password: str = Form(...)):
    try:
        auth_response = supabase.auth.sign_in_with_password({
            "email": email,
            "password": password
        })

        if not auth_response.session or not auth_response.user:
            return templates.TemplateResponse("login.html", {"request": request, "error": "Login failed"})

        # Redirect to chat page on success and set session cookie
        from fastapi.responses import RedirectResponse
        response = RedirectResponse(url="/chat", status_code=303)
        response.set_cookie(key="access_token", value=auth_response.session.access_token, httponly=True, secure=True)
        return response

    except Exception as e:
        return templates.TemplateResponse("login.html", {"request": request, "error": "Invalid credentials"})

@router.get("/logout")
def logout():
    from fastapi.responses import RedirectResponse
    response = RedirectResponse(url="/login", status_code=303)
    response.delete_cookie("access_token")
    return response
