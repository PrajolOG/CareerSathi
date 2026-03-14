from fastapi import APIRouter, Request, Depends
from fastapi.templating import Jinja2Templates
from app.database import supabase
from typing import Optional

router = APIRouter(prefix="/search", tags=["Search"])
templates = Jinja2Templates(directory="templates")

@router.get("/universities")
async def search_universities(request: Request, q: Optional[str] = None):
    # For now, we'll extract unique universities from Courses_DB
    query = supabase.table("Courses_DB").select("university_name, location").execute()
    
    # Simple deduplication
    unis = {}
    for item in query.data:
        name = item["university_name"]
        if name not in unis:
            unis[name] = item["location"]
    
    uni_list = [{"name": k, "location": v} for k, v in unis.items()]
    
    if q:
        uni_list = [u for u in uni_list if q.lower() in u["name"].lower() or q.lower() in u["location"].lower()]

    return templates.TemplateResponse("search_universities.html", {
        "request": request,
        "universities": uni_list,
        "query": q
    })

@router.get("/courses")
async def search_courses(request: Request, q: Optional[str] = None):
    query = supabase.table("Courses_DB").select("*")
    if q:
        # Simple ilike search on course name or category
        # FastAPI/Supabase-py syntax for ilike
        res = query.or_(f"course_name.ilike.%{q}%,career_category.ilike.%{q}%").execute()
    else:
        res = query.execute()

    return templates.TemplateResponse("search_courses.html", {
        "request": request,
        "courses": res.data,
        "query": q
    })
