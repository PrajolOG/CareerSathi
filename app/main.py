from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from app.routers import auth, chat, admin, reports, profile

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
    allow_origins=["*"],  # Allows all origins (for development)
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


@app.get("/", tags=["General"])
def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/terms", tags=["General"])
def read_terms(request: Request):
    return templates.TemplateResponse("terms.html", {"request": request})


@app.get("/welcome", tags=["General"])
def read_welcome(request: Request):
    if not request.cookies.get("signup_success"):
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url="/signup")
    return templates.TemplateResponse("newuserwelcome.html", {"request": request})