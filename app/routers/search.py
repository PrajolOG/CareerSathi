from fastapi import APIRouter, Request, HTTPException
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


def _get_authenticated_user(request: Request):
    access_token = request.cookies.get("access_token")
    if not access_token:
        raise HTTPException(status_code=401, detail="Unauthorized")

    try:
        user_response = supabase.auth.get_user(access_token)
        user = user_response.user
        if not user:
            raise ValueError("User not found")
        return user
    except Exception as exc:
        raise HTTPException(status_code=401, detail="Unauthorized") from exc


def _get_profile_context(user_id: str):
    try:
        profile_res = (
            supabase.table("Profiles")
            .select("full_name, profile_url")
            .eq("id", user_id)
            .single()
            .execute()
        )
        if profile_res.data:
            return profile_res.data.get("full_name"), profile_res.data.get("profile_url")
    except Exception as e:
        print(f"Error fetching profile context for search: {e}")

    return None, None


def _get_recommended_universities(user_id: str):
    try:
        report_res = (
            supabase.table("Reports")
            .select("career_prediction")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        if not report_res.data:
            return []

        prediction = report_res.data[0].get("career_prediction", "")
        top_recommendations = [career.strip() for career in prediction.split(",") if career.strip()][:3]
        if not top_recommendations:
            return []

        primary_prediction = top_recommendations[0]
        courses_res = (
            supabase.table("Courses_DB")
            .select("university_name, location, college_type, website_link")
            .ilike("career_category", f"%{primary_prediction}%")
            .execute()
        )
        if not courses_res.data:
            return []

        local_uni = None
        global_uni = None

        for item in courses_res.data:
            name = item["university_name"]
            loc = item["location"]
            c_type = item.get("college_type", "")
            website = _normalize_website(item.get("website_link") or "")

            is_local = c_type == "local" or any(
                x in loc.lower() for x in ["nepal", "kathmandu", "lalitpur", "pokhara", "dhulikhel"]
            )

            if is_local:
                if not local_uni or (not local_uni.get("website") and website):
                    local_uni = {
                        "name": name,
                        "location": loc,
                        "matched_career": primary_prediction,
                        "type": "Local",
                        "website": website,
                    }
            else:
                if not global_uni or (not global_uni.get("website") and website):
                    global_uni = {
                        "name": name,
                        "location": loc,
                        "matched_career": primary_prediction,
                        "type": "Global",
                        "website": website,
                    }

            if local_uni and global_uni:
                break

        recommendations = []
        if local_uni:
            recommendations.append(local_uni)
        if global_uni:
            recommendations.append(global_uni)
        return recommendations
    except Exception as e:
        print(f"Error fetching university recommendations for search: {e}")
        return []


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
    user = _get_authenticated_user(request)
    user_name, user_profile_pic = _get_profile_context(user.id)
    recommended_universities = _get_recommended_universities(user.id)

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
    user = _get_authenticated_user(request)
    user_name, user_profile_pic = _get_profile_context(user.id)

    query = supabase.table("Courses_DB").select(
        "course_name, university_name, location, college_type, career_category, website_link"
    )
    if q:
        term = q.strip()
        res = query.or_(
            f"course_name.ilike.%{term}%,"
            f"career_category.ilike.%{term}%,"
            f"university_name.ilike.%{term}%,"
            f"location.ilike.%{term}%,"
            f"college_type.ilike.%{term}%"
        ).execute()
    else:
        res = query.execute()

    courses = []
    for row in (res.data or []):
        college_type = (row.get("college_type") or "").strip().lower()
        courses.append({
            "course_name": (row.get("course_name") or "").strip() or "Course not specified",
            "university_name": (row.get("university_name") or "").strip() or "University not specified",
            "location": (row.get("location") or "").strip() or "Location not listed",
            "college_type": college_type if college_type in ["local", "global"] else "",
            "career_category": (row.get("career_category") or "").strip() or "General",
            "website_link": _normalize_website(row.get("website_link") or ""),
        })

    courses = sorted(courses, key=lambda x: (x["university_name"].lower(), x["course_name"].lower()))

    return templates.TemplateResponse("search_courses.html", {
        "request": request,
        "user_name": user_name,
        "user_profile_pic": user_profile_pic,
        "courses": courses,
        "courses_total": len(courses),
        "query": q or ""
    })
