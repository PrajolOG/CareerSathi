from fastapi import APIRouter, Request, Depends
from fastapi.templating import Jinja2Templates
from app.database import supabase
from typing import Optional

router = APIRouter(prefix="/search", tags=["Search"])
templates = Jinja2Templates(directory="templates")


def _normalize_website(link: str) -> str:
    clean = (link or "").strip()
    if clean and not (clean.startswith("http://") or clean.startswith("https://")):
        clean = f"https://{clean}"
    return clean


def _fetch_universities(q: Optional[str] = None):
    query = supabase.table("Courses_DB").select("university_name, location, college_type, website_link").execute()

    unis = {}
    for item in (query.data or []):
        name = (item.get("university_name") or "").strip()
        if not name:
            continue

        key = name.lower()
        location = (item.get("location") or "").strip()
        c_type = (item.get("college_type") or "").strip().lower()
        website = _normalize_website(item.get("website_link") or "")

        if key not in unis:
            unis[key] = {
                "name": name,
                "location": location,
                "type": c_type if c_type in ["local", "global"] else "",
                "website": website
            }
        else:
            if not unis[key]["location"] and location:
                unis[key]["location"] = location
            if not unis[key]["type"] and c_type in ["local", "global"]:
                unis[key]["type"] = c_type
            if not unis[key]["website"] and website:
                unis[key]["website"] = website

    uni_list = sorted(unis.values(), key=lambda x: x["name"].lower())

    if q:
        term = q.strip().lower()
        uni_list = [
            u for u in uni_list
            if term in u["name"].lower()
            or term in (u["location"] or "").lower()
            or term in (u.get("type") or "").lower()
        ]

    return uni_list

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
                    courses_res = supabase.table("Courses_DB").select("university_name, location, college_type, website_link").ilike("career_category", f"%{primary_prediction}%").execute()
                    if courses_res.data:
                        local_uni = None
                        global_uni = None
                        
                        for item in courses_res.data:
                            name = item["university_name"]
                            loc = item["location"]
                            c_type = item.get("college_type", "")
                            website = _normalize_website(item.get("website_link") or "")
                            
                            is_local = False
                            if c_type == "local" or any(x in loc.lower() for x in ["nepal", "kathmandu", "lalitpur", "pokhara", "dhulikhel"]):
                                is_local = True
                                
                            if is_local:
                                if not local_uni or (not local_uni.get("website") and website):
                                    local_uni = {
                                        "name": name,
                                        "location": loc,
                                        "matched_career": primary_prediction,
                                        "type": "Local",
                                        "website": website
                                    }
                            else:
                                if not global_uni or (not global_uni.get("website") and website):
                                    global_uni = {
                                        "name": name,
                                        "location": loc,
                                        "matched_career": primary_prediction,
                                        "type": "Global",
                                        "website": website
                                    }
                                
                            if local_uni and global_uni:
                                break
                                
                        if local_uni:
                            recommended_universities.append(local_uni)
                        if global_uni:
                            recommended_universities.append(global_uni)
        except Exception as e:
            print(f"Error fetching user or recommendations for search: {e}")

    uni_list = _fetch_universities(q)
    return templates.TemplateResponse("search_universities.html", {
        "request": request,
        "user_name": user_name,
        "user_profile_pic": user_profile_pic,
        "recommended_universities": recommended_universities,
        "universities": uni_list,
        "universities_total": len(uni_list),
        "query": q or ""
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
