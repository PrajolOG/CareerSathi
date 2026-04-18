from fastapi import APIRouter, Depends, Request, UploadFile, File
from fastapi.templating import Jinja2Templates
from app.routers.auth import verify_admin_status
from app.database import supabase, supabase_admin
from datetime import datetime, timedelta, timezone

# Adding Depends(verify_admin_status) here protects EVERY route in this file automatically!
router = APIRouter(prefix="/admin", tags=["Admin Dashboard"], dependencies=[Depends(verify_admin_status)])

templates = Jinja2Templates(directory="templates")

def format_nepal_time(utc_iso_str):
    if not utc_iso_str:
        return "Never"
    try:
        ts = str(utc_iso_str).replace("Z", "+00:00")
        utc_dt = datetime.fromisoformat(ts)
        nepal_dt = utc_dt.astimezone(timezone(timedelta(hours=5, minutes=45)))
        return nepal_dt.strftime("%Y-%m-%d %I:%M %p")
    except Exception:
        return str(utc_iso_str)[:16].replace('T', ' ')

templates.env.filters["nepal_time"] = format_nepal_time

@router.get("/dashboard")
def admin_dashboard(request: Request):
    # 1. Total Users
    users_res = supabase.table("Profiles").select("*", count="exact").execute()
    total_users = users_res.count if users_res.count is not None else 0
    
    # 2. Active (24h)
    yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    active_res = supabase.table("Profiles").select("id", count="exact").gt("last_active_at", yesterday).execute()
    active_sessions = active_res.count if active_res.count is not None else 0

    # 3. New Reports (24h)
    reports_res = supabase.table("Reports").select("id", count="exact").gt("created_at", yesterday).execute()
    new_reports = reports_res.count if reports_res.count is not None else 0

    # 4. Total Storage
    from app.minio_handler import minio_client
    storage_bytes = minio_client.get_total_storage_bytes()
    total_storage = f"{(storage_bytes / (1024 * 1024 * 1024)):.2f} GB" if storage_bytes > (1024 * 1024 * 1024) else f"{(storage_bytes / (1024 * 1024)):.2f} MB"

    # 5. Recent Chats (Latest 8)
    chat_res = supabase.table("Chat_History").select("message, created_at, sender, user_id").order("created_at", desc=True).limit(8).execute()
    recent_chats = chat_res.data or []
    for c in recent_chats:
        c["user_name"] = "Student"
        c["user_avatar"] = None

    # Add names
    uids = list(set(c["user_id"] for c in recent_chats if c.get("user_id")))
    if uids:
        names_res = supabase.table("Profiles").select("id, full_name, profile_url").in_("id", uids).execute()
        profile_map = {n["id"]: n for n in (names_res.data or [])}
        for c in recent_chats:
            user_profile = profile_map.get(c.get("user_id"), {})
            c["user_name"] = user_profile.get("full_name") or "Student"
            c["user_avatar"] = user_profile.get("profile_url")
    
    # 6. Chat Volume Graph (Last 30 Days)
    today = datetime.now(timezone.utc)
    thirty_days_ago = (today - timedelta(days=30)).isoformat()
    graph_res = supabase.table("Chat_History").select("created_at").gt("created_at", thirty_days_ago).execute()
    
    # Initialize 30 days of data
    chat_dates_all = {}
    for i in range(31): # 0 to 30 days ago
        d = (today - timedelta(days=i)).strftime("%Y-%m-%d")
        chat_dates_all[d] = 0
    
    for c in (graph_res.data or []):
        dt = c["created_at"][:10]
        if dt in chat_dates_all:
            chat_dates_all[dt] += 1
    
    # Sort all dates
    sorted_dates_30 = sorted(chat_dates_all.keys())
    chat_counts_30 = [chat_dates_all[d] for d in sorted_dates_30]
    
    # Slice for last 7 days
    sorted_dates_7 = sorted_dates_30[-7:]
    chat_counts_7 = chat_counts_30[-7:]

    # 8. Student Growth Stats (Image-style Card)
    # This week vs Last week
    fourteen_days_ago = (today - timedelta(days=14)).isoformat()
    growth_res = supabase.table("Profiles").select("created_at").gt("created_at", fourteen_days_ago).execute()
    
    this_week_count = 0
    last_week_count = 0
    daily_signups = { (today - timedelta(days=i)).strftime("%Y-%m-%d"): 0 for i in range(7) }
    
    cutoff_7 = today - timedelta(days=7)
    
    for p in (growth_res.data or []):
        ts = p["created_at"].replace("Z", "+00:00")
        created_at = datetime.fromisoformat(ts).replace(tzinfo=timezone.utc)
        date_str = created_at.strftime("%Y-%m-%d")
        
        if created_at > cutoff_7:
            this_week_count += 1
            if date_str in daily_signups:
                daily_signups[date_str] += 1
        else:
            last_week_count += 1
            
    # Calculate Growth %
    if last_week_count > 0:
        growth_percent = round(((this_week_count - last_week_count) / last_week_count) * 100, 1)
    else:
        growth_percent = 100.0 if this_week_count > 0 else 0.0
        
    # Format daily signups for bars (Oldest to Newest)
    signup_bars = [daily_signups[d] for d in sorted(daily_signups.keys())]
    # Normalize for CSS heights (max height 40px)
    max_val = max(signup_bars) if signup_bars and max(signup_bars) > 0 else 1
    signup_heights = [int((v / max_val) * 40) for v in signup_bars]

    # 7. Career Distribution
    all_reports = supabase.table("Reports").select("career_prediction").execute()
    career_counts = {}
    for r in (all_reports.data or []):
        pred = r.get("career_prediction", "")
        if pred:
            # career_prediction is like "Software Engineering, Data Science"
            first_career = pred.split(",")[0].strip()
            career_counts[first_career] = career_counts.get(first_career, 0) + 1
    
    # Get top 5 careers for pie chart
    sorted_careers = sorted(career_counts.items(), key=lambda x: x[1], reverse=True)[:5]
    career_labels = [x[0] for x in sorted_careers]
    career_values = [x[1] for x in sorted_careers]

    # 9. University Database Coverage (Local vs Global)
    uni_res = supabase.table("Courses_DB").select("college_type").execute()
    uni_data_raw = uni_res.data or []
    local_c = sum(1 for x in uni_data_raw if x.get("college_type") == "local")
    global_c = sum(1 for x in uni_data_raw if x.get("college_type") == "global")
    university_labels = ["Local", "Global"]
    university_data = [local_c, global_c]

    # 10. Model Performance Metrics (Latency)
    avg_ml = 0
    avg_ai = 0
    avg_total = 0
    ml_trend = [0] * 7
    ai_trend = [0] * 7
    
    try:
        perf_res = supabase.table("Reports").select("ml_latency_ms, ai_latency_ms, total_latency_ms, created_at").order("created_at", desc=True).limit(100).execute()
        perf_data = perf_res.data or []
        
        if perf_data:
            avg_ml = int(sum(r.get("ml_latency_ms", 0) for r in perf_data) / len(perf_data))
            avg_ai = int(sum(r.get("ai_latency_ms", 0) for r in perf_data) / len(perf_data))
            avg_total = int(sum(r.get("total_latency_ms", 0) for r in perf_data) / len(perf_data))

            # Latency Trend (Last 7 Days)
            latency_dates = sorted_dates_7
            ml_trend = []
            ai_trend = []
            
            for d in latency_dates:
                day_reports = [r for r in perf_data if r["created_at"][:10] == d]
                if day_reports:
                    ml_trend.append(int(sum(r.get("ml_latency_ms", 0) for r in day_reports) / len(day_reports)))
                    ai_trend.append(int(sum(r.get("ai_latency_ms", 0) for r in day_reports) / len(day_reports)))
                else:
                    ml_trend.append(0)
                    ai_trend.append(0)
    except Exception as e:
        print(f"Latency stats fetch failed (expected if DB not updated): {e}")

    return templates.TemplateResponse("admin/dashboard.html", {
        "request": request, 
        "total_users": total_users, 
        "active_sessions": active_sessions,
        "new_reports": new_reports,
        "total_storage": total_storage,
        "recent_chats": recent_chats,
        "chart_dates_week": sorted_dates_7,
        "chat_counts_week": chat_counts_7,
        "chart_dates_month": sorted_dates_30,
        "chat_counts_month": chat_counts_30,
        "career_labels": career_labels,
        "career_values": career_values,
        "university_labels": university_labels,
        "university_data": university_data,
        "growth_percent": growth_percent,
        "signup_heights": signup_heights,
        "avg_ml_latency": avg_ml,
        "avg_ai_latency": avg_ai,
        "avg_total_latency": avg_total,
        "ml_trend": ml_trend,
        "ai_trend": ai_trend,
        "message": "Welcome Admin!"
    })

@router.get("/users")
def get_all_users(request: Request):
    # Admin viewing all students
    users_res = supabase.table("Profiles").select("*").execute()
    users = users_res.data
    return templates.TemplateResponse("admin/users.html", {
        "request": request,
        "users": users
    })

@router.get("/universities")
def get_all_universities(request: Request):
    # Admin viewing all universities/courses
    courses_res = supabase.table("Courses_DB").select("*").order("id", desc=True).execute()
    courses = courses_res.data
    return templates.TemplateResponse("admin/universities.html", {
        "request": request,
        "courses": courses
    })

@router.post("/api/universities")
async def add_university(request: Request):
    data = await request.json()
    res = supabase.table("Courses_DB").insert(data).execute()
    return {"success": True, "data": res.data}

@router.put("/api/universities/{uid}")
async def update_university(request: Request, uid: int):
    data = await request.json()
    res = supabase.table("Courses_DB").update(data).eq("id", uid).execute()
    return {"success": True, "data": res.data}

@router.post("/api/universities/delete")
async def delete_universities(request: Request):
    data = await request.json()
    ids = data.get("ids", [])
    if ids:
        # bulk delete by ID
        res = supabase.table("Courses_DB").delete().in_("id", ids).execute()
        return {"success": True, "data": res.data}
    return {"success": False, "message": "No IDs provided"}

# ---------- User Detail Page ----------

@router.get("/users/{user_id}")
def get_user_detail(request: Request, user_id: str):
    """Full user insights page for admin."""
    # Profile
    profile_res = supabase.table("Profiles").select("*").eq("id", user_id).maybe_single().execute()
    if not profile_res.data:
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url="/admin/users", status_code=303)
    profile = profile_res.data

    # Reports
    reports_res = supabase.table("Reports").select("id, career_prediction, created_at").eq("user_id", user_id).order("created_at", desc=True).execute()
    reports = reports_res.data or []

    # Chat History (last 100 messages)
    chat_res = supabase.table("Chat_History").select("message, sender, created_at").eq("user_id", user_id).order("created_at", desc=False).limit(100).execute()
    chats = chat_res.data or []

    # User Features (ML input data)
    features = None
    try:
        feat_res = supabase.table("User_Features").select("*").eq("user_id", user_id).maybe_single().execute()
        features = feat_res.data
    except Exception:
        pass

    return templates.TemplateResponse("admin/user_detail.html", {
        "request": request,
        "profile": profile,
        "user_id": user_id,
        "reports": reports,
        "chats": chats,
        "features": features,
        "education_levels": [
            {"label": "High School (+2 Science)", "value": "High School (+2 Science)", "icon": "fa-flask"},
            {"label": "High School (+2 Management)", "value": "High School (+2 Management)", "icon": "fa-briefcase"},
            {"label": "A-Levels", "value": "A-Levels", "icon": "fa-scroll"},
            {"label": "Bachelors (Undergraduate)", "value": "Bachelors (Undergraduate)", "icon": "fa-university"},
            {"label": "Masters (Postgraduate)", "value": "Masters (Postgraduate)", "icon": "fa-award"}
        ]
    })

@router.put("/api/users/{user_id}")
async def update_user_profile(request: Request, user_id: str):
    data = await request.json()
    allowed = {k: v for k, v in data.items() if k in ("full_name", "gender", "grade_level", "role", "status")}
    res = supabase.table("Profiles").update(allowed).eq("id", user_id).execute()
    return {"success": True, "data": res.data}

@router.delete("/api/users/{user_id}")
async def delete_user(request: Request, user_id: str):
    """
    Deletes direct from auth.users using the admin client. 
    The database triggers ON DELETE CASCADE for Profiles, Reports, Chat etc.
    """
    if not supabase_admin:
        return {"success": False, "message": "Admin client not configured"}

    try:
        # This deletes the user from Supabase Auth
        # It triggers the cascading delete in SQL
        supabase_admin.auth.admin.delete_user(user_id)
        return {"success": True}
    except Exception as e:
        print(f"Error deleting user {user_id}: {e}")
        return {"success": False, "message": str(e)}


from app.minio_handler import minio_client

@router.get("/database")
def admin_database(request: Request):
    """View all MinIO buckets."""
    buckets = minio_client.list_buckets()
    return templates.TemplateResponse("admin/database.html", {
        "request": request,
        "buckets": buckets
    })

@router.get("/database/{bucket_name}")
def admin_bucket_detail(request: Request, bucket_name: str):
    """View objects within a specific MinIO bucket."""
    objects = minio_client.list_bucket_objects(bucket_name)
    all_buckets = minio_client.list_buckets()
    target_buckets = [b["name"] for b in all_buckets if b["name"] != bucket_name]
    
    return templates.TemplateResponse("admin/bucket_detail.html", {
        "request": request,
        "bucket_name": bucket_name,
        "objects": objects,
        "target_buckets": target_buckets
    })

@router.post("/api/buckets")
async def create_bucket(request: Request):
    data = await request.json()
    bucket_name = data.get("name")
    if not bucket_name:
        return {"success": False, "message": "Bucket name is required"}
    
    success, msg = minio_client.create_bucket(bucket_name)
    return {"success": success, "message": msg}

@router.post("/api/buckets/migrate")
async def migrate_bucket(request: Request):
    data = await request.json()
    source = data.get("source")
    target = data.get("target")
    objects = data.get("objects")

    if not source or not target:
        return {"success": False, "message": "Source and target buckets are required"}
    
    success, msg = minio_client.migrate_bucket(source, target, objects_to_migrate=objects)
    return {"success": success, "message": msg}

@router.delete("/api/buckets/{bucket_name}")
async def delete_bucket(request: Request, bucket_name: str):
    success, msg = minio_client.delete_bucket(bucket_name)
    return {"success": success, "message": msg}

@router.post("/api/buckets/{bucket_name}/upload")
async def upload_objects(bucket_name: str, files: list[UploadFile] = File(...)):
    for file in files:
        data = await file.read()
        minio_client.upload_file(bucket_name, file.filename, data, file.content_type)
    return {"success": True, "message": "Files uploaded successfully"}

@router.delete("/api/buckets/{bucket_name}/objects")
async def delete_objects(bucket_name: str, request: Request):
    data = await request.json()
    objects = data.get("objects", [])
    if not objects:
        return {"success": False, "message": "No objects provided for deletion"}
    success, msg = minio_client.delete_objects(bucket_name, objects)
    return {"success": success, "message": msg}
