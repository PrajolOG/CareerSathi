from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from app.routers import auth, chat, admin, reports, profile, search
import time, asyncio

from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

app = FastAPI(
    title="Career Sathi API",
    description="Backend for FYP Career Counselor System",
    version="1.0.0"
)

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include the routers created
app.include_router(auth.router)
app.include_router(chat.router)
app.include_router(admin.router)
app.include_router(reports.router)
app.include_router(profile.router)
app.include_router(search.router)

# ---------- Last-Active Tracker Middleware ----------
_last_active_cache: dict[str, float] = {}   # user_id -> last stamp time
COOLDOWN_SECONDS = 300  # only hit DB once per 5 minutes per user

def _stamp_last_active(user_id: str):
    """Synchronous DB call – runs in a thread so it never blocks requests."""
    from app.database import supabase
    from datetime import datetime, timezone
    try:
        supabase.table("Profiles").update(
            {"last_active_at": datetime.now(timezone.utc).isoformat()}
        ).eq("id", user_id).execute()
    except Exception:
        pass  # silent – never break the user's request

class LastActiveMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        # Fire-and-forget: try to stamp activity after the response is ready
        token = request.cookies.get("access_token")
        if token:
            try:
                from app.database import supabase
                user_res = supabase.auth.get_user(token)
                uid = user_res.user.id
                now = time.time()
                if now - _last_active_cache.get(uid, 0) > COOLDOWN_SECONDS:
                    _last_active_cache[uid] = now
                    asyncio.get_event_loop().run_in_executor(None, _stamp_last_active, uid)
            except Exception:
                pass
        return response

app.add_middleware(LastActiveMiddleware)


@app.get("/", tags=["General"])
def read_root(request: Request):
    access_token = request.cookies.get("access_token")
    user_name = None
    user_profile_pic = None
    
    if access_token:
        try:
            # Import supabase inside the function to avoid potential circular imports if models are moved
            from app.database import supabase
            user_response = supabase.auth.get_user(access_token)
            if user_response and user_response.user:
                user = user_response.user
                profile_res = supabase.table("Profiles").select("full_name, profile_url").eq("id", user.id).single().execute()
                if profile_res.data:
                    user_name = profile_res.data.get("full_name")
                    user_profile_pic = profile_res.data.get("profile_url")
        except Exception as e:
            print(f"Error fetching user for index: {e}")
            
    return templates.TemplateResponse("index.html", {
        "request": request,
        "user_name": user_name,
        "user_profile_pic": user_profile_pic
    })


@app.get("/terms", tags=["General"])
def read_terms(request: Request):
    return templates.TemplateResponse("terms.html", {"request": request})


@app.get("/privacy", tags=["General"])
def read_privacy(request: Request):
    return templates.TemplateResponse("privacy.html", {"request": request})


@app.get("/welcome", tags=["General"])
def read_welcome(request: Request):
    if not request.cookies.get("signup_success"):
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url="/signup")
    return templates.TemplateResponse("newuserwelcome.html", {"request": request})