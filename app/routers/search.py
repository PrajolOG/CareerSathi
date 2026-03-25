from fastapi import APIRouter, Request, Depends
from fastapi.templating import Jinja2Templates
from app.database import supabase
from typing import Optional

router = APIRouter(prefix="/search", tags=["Search"])
templates = Jinja2Templates(directory="templates")

@router.get("/universities")
async def search_universities(request: Request, q: Optional[str] = None):
    access_token = request.cookies.get("access_token")
    user_name = None
    user_profile_pic = None
    recommended_universities = []
    
    if access_token:
        try:
            user_response = supabase.auth.get_user(access_token)
            user = user_response.user
            profile_res = supabase.table("Profiles").select("full_name, profile_url").eq("id", user.id).single().execute()
            if profile_res.data:
                user_name = profile_res.data.get("full_name")
                user_profile_pic = profile_res.data.get("profile_url")
                
            # Fetch latest AI report for the user
            report_res = supabase.table("Reports").select("career_prediction").eq("user_id", user.id).order("created_at", desc=True).limit(1).execute()
            if report_res.data and len(report_res.data) > 0:
                prediction = report_res.data[0].get("career_prediction", "")
                top_recommendations = [career.strip() for career in prediction.split(",") if career.strip()][:3]
                if top_recommendations:
                    primary_prediction = top_recommendations[0]
                    # Query courses related to the top career prediction
                    courses_res = supabase.table("Courses_DB").select("university_name, location, college_type").ilike("career_category", f"%{primary_prediction}%").execute()
                    if courses_res.data:
                        local_uni = None
                        global_uni = None
                        
                        for item in courses_res.data:
                            name = item["university_name"]
                            loc = item["location"]
                            c_type = item.get("college_type", "")
                            
                            is_local = False
                            if c_type == "local" or any(x in loc.lower() for x in ["nepal", "kathmandu", "lalitpur", "pokhara", "dhulikhel"]):
                                is_local = True
                                
                            if is_local and not local_uni:
                                local_uni = {"name": name, "location": loc, "matched_career": primary_prediction, "type": "Local"}
                            elif not is_local and not global_uni:
                                global_uni = {"name": name, "location": loc, "matched_career": primary_prediction, "type": "Global"}
                                
                            if local_uni and global_uni:
                                break
                                
                        if local_uni:
                            recommended_universities.append(local_uni)
                        if global_uni:
                            recommended_universities.append(global_uni)
        except Exception as e:
            print(f"Error fetching user or recommendations for search: {e}")

    # Extract unique universities from Courses_DB for the general list
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
        "user_name": user_name,
        "user_profile_pic": user_profile_pic,
        "recommended_universities": recommended_universities,
        "universities": uni_list,
        "query": q
    })

@router.get("/courses")
async def search_courses(request: Request, q: Optional[str] = None):
    access_token = request.cookies.get("access_token")
    user_name = None
    user_profile_pic = None
    
    if access_token:
        try:
            user_response = supabase.auth.get_user(access_token)
            user = user_response.user
            profile_res = supabase.table("Profiles").select("full_name, profile_url").eq("id", user.id).single().execute()
            if profile_res.data:
                user_name = profile_res.data.get("full_name")
                user_profile_pic = profile_res.data.get("profile_url")
        except Exception:
            pass

    query = supabase.table("Courses_DB").select("*")
    if q:
        res = query.or_(f"course_name.ilike.%{q}%,career_category.ilike.%{q}%").execute()
    else:
        res = query.execute()

    return templates.TemplateResponse("search_courses.html", {
        "request": request,
        "user_name": user_name,
        "user_profile_pic": user_profile_pic,
        "courses": res.data,
        "query": q
    })
