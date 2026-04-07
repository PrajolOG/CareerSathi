from fastapi import APIRouter, HTTPException, Request, Form, BackgroundTasks
from fastapi.templating import Jinja2Templates
from app.database import supabase
from app.services.password_reset_service import password_reset_service
from app.services.email_service import email_service
from app.rate_limiter import check_login_rate_limit

router = APIRouter(tags=["Authentication"])
templates = Jinja2Templates(directory="templates")


def _forgot_password_context(request: Request, **extra):
    context = {
        "request": request,
        "stage": "request",
        "email_value": "",
        "message": None,
        "error": None,
    }
    context.update(extra)
    return context

def verify_admin_status(request: Request):
    access_token = request.cookies.get("access_token")
    if not access_token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    try:
        user_res = supabase.auth.get_user(access_token)
        user = user_res.user
        
        # Check Profiles table
        profile_res = supabase.table("Profiles").select("role, status").eq("id", user.id).single().execute()
        if not profile_res.data or profile_res.data.get("role") != "admin" or profile_res.data.get("status") == "deactivated":
            raise HTTPException(status_code=401, detail="Access denied")
            
        return user
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=401, detail="Invalid token") from exc

@router.get("/signup")
def signup_page(request: Request):
    return templates.TemplateResponse("signup.html", {"request": request})

@router.post("/signup")
def signup(
    request: Request,
    background_tasks: BackgroundTasks,
    email: str = Form(...),
    password: str = Form(...),
    full_name: str = Form(...),
    grade_level: str = Form(...),
    gender: str = Form(...)
):
    # Rate limit: 5 signups per minute per IP
    client_ip = request.client.host if request.client else "unknown"
    allowed, retry_after = check_login_rate_limit(client_ip)
    if not allowed:
        return templates.TemplateResponse("signup.html", {
            "request": request,
            "error": f"Too many attempts. Please try again in {retry_after} seconds."
        })

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
            response.set_cookie(key="access_token", value=auth_response.session.access_token, httponly=True, secure=False, samesite="lax", max_age=604800)
            
        # Send welcome email asynchronously
        background_tasks.add_task(email_service.send_welcome_email, email, full_name)

        return response

    except Exception as e:
        return templates.TemplateResponse("signup.html", {"request": request, "error": str(e)})


@router.get("/login")
def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})


@router.get("/forgot-password")
def forgot_password_page(request: Request):
    return templates.TemplateResponse(
        "forgot_password.html",
        _forgot_password_context(request),
    )


@router.post("/forgot-password/send-otp")
def forgot_password_send_otp(request: Request, email: str = Form(...)):
    email_value = (email or "").strip()
    success, feedback = password_reset_service.send_reset_otp(email_value)

    return templates.TemplateResponse(
        "forgot_password.html",
        _forgot_password_context(
            request,
            stage="verify" if success else "request",
            email_value=email_value,
            message=feedback if success else None,
            error=None if success else feedback,
        ),
    )


@router.post("/forgot-password/reset")
def forgot_password_reset(
    request: Request,
    email: str = Form(...),
    otp: str = Form(...),
    new_password: str = Form(...),
    confirm_password: str = Form(...),
):
    email_value = (email or "").strip()

    if new_password != confirm_password:
        return templates.TemplateResponse(
            "forgot_password.html",
            _forgot_password_context(
                request,
                stage="verify",
                email_value=email_value,
                error="Passwords do not match.",
            ),
        )

    success, feedback = password_reset_service.reset_password(email_value, otp, new_password)
    if not success:
        return templates.TemplateResponse(
            "forgot_password.html",
            _forgot_password_context(
                request,
                stage="verify",
                email_value=email_value,
                error=feedback,
            ),
        )

    return templates.TemplateResponse(
        "login.html",
        {
            "request": request,
            "message": feedback,
        },
    )

@router.post("/login")
def login(request: Request, email: str = Form(...), password: str = Form(...)):
    # Rate limit: 5 login attempts per minute per IP
    client_ip = request.client.host if request.client else "unknown"
    allowed, retry_after = check_login_rate_limit(client_ip)
    if not allowed:
        return templates.TemplateResponse("login.html", {
            "request": request,
            "error": f"Too many login attempts. Please try again in {retry_after} seconds."
        })

    try:
        auth_response = supabase.auth.sign_in_with_password({
            "email": email,
            "password": password
        })

        if not auth_response.session or not auth_response.user:
            return templates.TemplateResponse("login.html", {"request": request, "error": "Login failed"})

        # Check role and status from Profiles table
        try:
            profile_check = supabase.table("Profiles").select("role, status").eq("id", auth_response.user.id).single().execute()
            
            if profile_check.data.get("status") == "deactivated":
                return templates.TemplateResponse("login.html", {
                    "request": request, 
                    "error": "Your account has been deactivated. Please contact support."
                })
                
            is_admin = profile_check.data.get("role") == "admin"
        except Exception:
            is_admin = False
            
        redirect_url = "/admin/dashboard" if is_admin else "/userProfile"

        from fastapi.responses import RedirectResponse
        response = RedirectResponse(url=redirect_url, status_code=303)
        response.set_cookie(key="access_token", value=auth_response.session.access_token, httponly=True, secure=False, samesite="lax", max_age=604800)
        return response

    except Exception as e:
        return templates.TemplateResponse("login.html", {"request": request, "error": "Invalid credentials"})

@router.get("/logout")
def logout():
    from fastapi.responses import RedirectResponse
    response = RedirectResponse(url="/login", status_code=303)
    response.delete_cookie("access_token")
    return response
