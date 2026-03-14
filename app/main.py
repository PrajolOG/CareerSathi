from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from app.routers import auth, chat, admin, reports, profile, search

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


@app.get("/", tags=["General"])
def read_root(request: Request):
    access_token = request.cookies.get("access_token")
    user_name = None
    user_avatar = None
    
    if access_token:
        try:
            # Import supabase inside the function to avoid potential circular imports if models are moved
            from app.database import supabase
            user_response = supabase.auth.get_user(access_token)
            if user_response and user_response.user:
                user = user_response.user
                profile_res = supabase.table("Profiles").select("full_name").eq("id", user.id).single().execute()
                if profile_res.data:
                    user_name = profile_res.data.get("full_name")
                # Default avatar if not in schema yet
                user_avatar = "https://icons.veryicon.com/png/o/miscellaneous/user-avatar/user-avatar-male-5.png"
        except Exception as e:
            print(f"Error fetching user for index: {e}")
            
    return templates.TemplateResponse("index.html", {
        "request": request,
        "user_name": user_name,
        "user_avatar": user_avatar
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