from fastapi import APIRouter, Request, HTTPException, BackgroundTasks
from fastapi.templating import Jinja2Templates
from fastapi.responses import JSONResponse, RedirectResponse
from app.database import supabase, url, key
from supabase import create_client, ClientOptions
from datetime import datetime
from app.schemas import ReportGenerationRequest
import json
from app.services.ml_service import predict_career
from app.services.gemini_pool import gemini_pool
import time

router = APIRouter(tags=["Student Reports"])
templates = Jinja2Templates(directory="templates")

def format_iso_date(iso_str):
    try:
        dt = datetime.fromisoformat(iso_str.replace('Z', '+00:00'))
        return dt.strftime("%B %d, %Y")
    except:
        return "Unknown Date"

def parse_json_maybe(raw_value, default):
    if raw_value is None:
        return default
    if isinstance(raw_value, (list, dict)):
        return raw_value
    if isinstance(raw_value, str):
        txt = raw_value.strip()
        if not txt:
            return default
        try:
            parsed = json.loads(txt)
            if isinstance(parsed, str):
                parsed = json.loads(parsed)
            return parsed
        except Exception:
            return default
    return default

async def process_report_background(report_data: ReportGenerationRequest, user_id: str, access_token: str):
    """Heavy lifting logic moved to background to prevent UI blocking."""
    try:
        # Create scoped client for the background session
        auth_client = create_client(
            url, 
            key, 
            options=ClientOptions(headers={"Authorization": f"Bearer {access_token}"})
        )
        
        # Start total timer
        start_total = time.perf_counter_ns()
        
        # 1. Predict career using ML service
        start_ml = time.perf_counter_ns()
        ml_input = report_data.model_dump()
        top_recommendations = predict_career(ml_input)
        end_ml = time.perf_counter_ns()
        ml_latency = (end_ml - start_ml) // 1_000_000 # Convert to ms
        
        if isinstance(top_recommendations, str):
            top_recommendations = [top_recommendations]
        top_recommendations = [career for career in top_recommendations if career]
        career_prediction_text = ", ".join(top_recommendations[:3]) if top_recommendations else "Software Engineering"
        
        # 2. Save User Features (Same as before)
        features_data = {
            "user_id": user_id,
            "city_type": report_data.general_info.city_type,
            "family_income": report_data.general_info.family_income,
            "plus2_stream": report_data.general_info.plus2_stream,
            "plus2_gpa": float(report_data.general_info.plus2_gpa),
            
            "grade_english": report_data.grades.english,
            "grade_nepali": report_data.grades.nepali,
            "grade_social": report_data.grades.social,
            "grade_math": report_data.grades.math,
            "grade_physics": report_data.grades.physics,
            "grade_chemistry": report_data.grades.chemistry,
            "grade_biology": report_data.grades.biology,
            "grade_computer": report_data.grades.computer,
            "grade_accounts": report_data.grades.accounts,
            "grade_economics": report_data.grades.economics,
            "grade_law": report_data.grades.law,

            "interest_technology": report_data.interests.technology,
            "interest_math_stats": report_data.interests.math_stats,
            "interest_art_design": report_data.interests.art_design,
            "interest_business_money": report_data.interests.business_money,
            "interest_social_people": report_data.interests.social_people,
            "interest_bio_health": report_data.interests.bio_health,
            "interest_nature_agri": report_data.interests.nature_agri,
            "interest_construction": report_data.interests.construction,
            "interest_law_politics": report_data.interests.law_politics,
            "interest_hospitality_food": report_data.interests.hospitality_food,
            "interest_gaming_entertainment": report_data.interests.gaming_entertainment,
            "interest_history_culture": report_data.interests.history_culture,

            "score_ioe": report_data.entrance_scores.ioe,
            "score_cee": report_data.entrance_scores.cee,
            "score_cmat": report_data.entrance_scores.cmat
        }
        
        try:
             auth_client.table("User_Features").upsert(features_data).execute()
        except Exception as embed_e:
             print(f"Error saving user features background: {embed_e}")
             
        # 3. AI Enrichment (Gemini)
        start_ai = time.perf_counter_ns()
        enriched_data = {"matching_factors": [], "roadmaps": []}
        try:
            enrich_prompt = f"""
            Identify the career match for a student with this profile:
            - Plus2 Stream: {report_data.general_info.plus2_stream} (GPA: {report_data.general_info.plus2_gpa})
            - Top Interests: {report_data.interests}
            - Entrance Scores: IOE={report_data.entrance_scores.ioe}, CEE={report_data.entrance_scores.cee}, CMAT={report_data.entrance_scores.cmat}
            - Grades: {report_data.grades}

            The ML Model has predicted these Top 3 Careers: {career_prediction_text}

            TASK:
            For each of these 3 careers, provide:
            1. matching_factors (list of strings): Provide 3 specific bullet points (sentences) explaining WHY this career fits this student based on their grades, stream, and interests.
            2. A roadmap (object): 4 phases (Foundation, Core Skills, Specialization, Career Entry) with 3 specific steps each (format as "Title: Description"). Use icons from FontAwesome (e.g., fa-code, fa-seedling). For each phase, also provide a relevant 'course_recommendation' object with a 'name' and 'link' that would help the student achieve that phase.

            OUTPUT FORMAT (Strict JSON):
            {{
                "matching_factors": [
                    ["Point 1 for career 1", "Point 2 for career 1", "Point 3 for career 1"],
                    ["Point 1 for career 2", "Point 2 for career 2", "Point 3 for career 2"],
                    ["Point 1 for career 3", "Point 2 for career 3", "Point 3 for career 3"]
                ],
                "roadmaps": [
                    {{
                        "career": "Name",
                        "phases": [
                            {{ 
                                "title": "Foundation", 
                                "icon": "fa-seedling", 
                                "color": "#10B981", 
                                "steps": ["step1", "step2", "step3"],
                                "course_recommendation": {{
                                    "name": "Introduction to Economics",
                                    "link": "https://coursera.org/..."
                                }}
                            }},
                            ...3 more phases
                        ]
                    }},
                    ...2 more roadmaps
                ]
            }}
            """
            
            gemini_res = await gemini_pool.generate_content(
                prompt=enrich_prompt,
                system_instruction="You are an expert career advisor. Return ONLY raw valid JSON."
            )
            raw_text = gemini_res.text.strip()
            if "```json" in raw_text:
                raw_text = raw_text.split("```json")[1].split("```")[0].strip()
            enriched_data = json.loads(raw_text)
        except Exception as ai_e:
            print(f"AI Enrichment background failed: {ai_e}")
        
        end_ai = time.perf_counter_ns()
        ai_latency = (end_ai - start_ai) // 1_000_000
        end_total = time.perf_counter_ns()
        total_latency = (end_total - start_total) // 1_000_000

        # 4. Save to Reports
        matching_factors = enriched_data.get("matching_factors", ["Matches based on academic profile and interests"])
        roadmaps = enriched_data.get("roadmaps", [])
        
        new_report = {
            "user_id": user_id,
            "career_prediction": career_prediction_text,
            "matching_factor": json.dumps(matching_factors), # Store reasons as JSON array
            "roadmap": roadmaps, # Store ONLY roadmaps list
            "ml_latency_ms": ml_latency,
            "ai_latency_ms": ai_latency,
            "total_latency_ms": total_latency
        }
        auth_client.table("Reports").insert(new_report).execute()
        print(f"Successfully generated background report for user {user_id}")

    except Exception as e:
        print(f"BACKGROUND TASK ERROR: {e}")

@router.post("/reports/generate")
async def generate_report(request: Request, report_data: ReportGenerationRequest, background_tasks: BackgroundTasks):
    access_token = request.cookies.get("access_token")
    if not access_token:
        raise HTTPException(status_code=401, detail="Unauthorized")

    try:
        user_response = supabase.auth.get_user(access_token)
        user = user_response.user
        
        # 0. Check Usage Limits (Max 3 reports)
        existing_reports = supabase.table("Reports").select("id", count="exact").eq("user_id", user.id).execute()
        report_count = existing_reports.count if existing_reports.count is not None else 0
        
        if report_count >= 3:
            raise HTTPException(
                status_code=403, 
                detail="You have reached the maximum limit of 3 career reports. Please delete an older report to generate a new one."
            )

        # Start the background task
        background_tasks.add_task(process_report_background, report_data, user.id, access_token)
        
        # Return immediately
        return JSONResponse(status_code=202, content={
            "status": "success", 
            "message": "Career report generation started in the background. It will appear in your reports list shortly."
        })
            
    except HTTPException as he:
        # Re-raise HTTP exceptions (like our 403 limit)
        raise he
    except Exception as e:
        print(f"Error starting background report: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/reports")
async def get_reports_list(request: Request):
    access_token = request.cookies.get("access_token")
    if not access_token:
        raise HTTPException(status_code=401, detail="Unauthorized")

    try:
        user_response = supabase.auth.get_user(access_token)
        user = user_response.user
    except Exception as e:
        print(f"Auth failed in reports list: {e}")
        raise HTTPException(status_code=401, detail="Unauthorized") from e

    try:
        # Fetch profile
        profile = supabase.table("Profiles").select("*").eq("id", user.id).single().execute()
        user_name = profile.data.get("full_name", "User")
        user_profile_pic = profile.data.get("profile_url")

        # Fetch all reports for the user
        reports_res = supabase.table("Reports").select("*").eq("user_id", user.id).order("created_at", desc=True).execute()
        
        reports_list = []
        for r in reports_res.data:
            r['formatted_date'] = format_iso_date(r.get('created_at', ''))
            reports_list.append(r)

        return templates.TemplateResponse("reports.html", {
            "request": request,
            "user_name": user_name,
            "user_profile_pic": user_profile_pic,
            "reports": reports_list
        })
        
    except Exception as e:
        print(f"Error loading reports list data: {e}")
        raise HTTPException(status_code=500, detail="Failed to load reports. Please try again.")

@router.get("/reports/{report_id}")
async def get_report_details(request: Request, report_id: str):
    access_token = request.cookies.get("access_token")
    if not access_token:
        raise HTTPException(status_code=401, detail="Unauthorized")

    try:
        user_response = supabase.auth.get_user(access_token)
        user = user_response.user
    except Exception as e:
        print(f"Auth failed in report details: {e}")
        raise HTTPException(status_code=401, detail="Unauthorized") from e

    try:
        # Fetch profile
        profile = supabase.table("Profiles").select("*").eq("id", user.id).single().execute()
        user_name = profile.data.get("full_name", "User")
        user_profile_pic = profile.data.get("profile_url")

        # Fetch the specific report
        query = supabase.table("Reports").select("*").eq("id", report_id)
        
        # If not admin, restrict to own reports
        if profile.data.get("role") != "admin":
            query = query.eq("user_id", user.id)
            
        report_res = query.maybe_single().execute()
        
        if not report_res.data:
            return RedirectResponse(url="/reports")
            
        report = report_res.data
        
        # Fetch user features for the radar chart
        user_features = {}
        try:
            feat_res = supabase.table("User_Features").select("*").eq("user_id", report.get("user_id")).maybe_single().execute()
            user_features = feat_res.data or {}
        except Exception as e:
            print(f"Error fetching user features for radar: {e}")

        formatted_date = format_iso_date(report.get("created_at", ""))
        prediction = report.get("career_prediction", "Software Engineering")
        top_recommendations = [career.strip() for career in prediction.split(",") if career.strip()][:3]
        if not top_recommendations:
            top_recommendations = ["Software Engineering"]

        career_options = []
        for idx, career_name in enumerate(top_recommendations):
            courses_res = supabase.table("Courses_DB").select("*").ilike("career_category", f"%{career_name}%").execute()

            nepal_courses = []
            global_courses = []

            if courses_res.data:
                for c in courses_res.data:
                    # Use college_type column for strict categorization
                    ctype = str(c.get("college_type", "local")).lower()
                    if ctype == "local":
                        nepal_courses.append(c)
                    else:
                        global_courses.append(c)

            career_options.append({
                "rank": idx + 1,
                "career": career_name,
                "nepal_courses": nepal_courses,
                "global_courses": global_courses
            })

        primary_prediction = career_options[0]["career"]
        nepal_courses = career_options[0]["nepal_courses"]
        global_courses = career_options[0]["global_courses"]

        return templates.TemplateResponse("reports_details.html", {
            "request": request,
            "user_name": user_name,
            "user_profile_pic": user_profile_pic,
            "report": report,
            "top_recommendations": top_recommendations,
            "career_options": career_options,
            "primary_prediction": primary_prediction,
            "formatted_date": formatted_date,
            "nepal_courses": nepal_courses,
            "global_courses": global_courses,
            "user_features": user_features
        })
        
    except HTTPException as he:
        raise he
    except Exception as e:
        print(f"Error loading report details data: {e}")
        raise HTTPException(status_code=500, detail="Failed to load report details.")

@router.get("/reports/{report_id}/pdf-preview")
async def get_report_pdf_preview(request: Request, report_id: str):
    access_token = request.cookies.get("access_token")
    if not access_token:
        raise HTTPException(status_code=401, detail="Unauthorized")

    try:
        user_response = supabase.auth.get_user(access_token)
        user = user_response.user
    except Exception as e:
        print(f"Auth failed in report pdf preview: {e}")
        raise HTTPException(status_code=401, detail="Unauthorized") from e

    try:
        profile = supabase.table("Profiles").select("*").eq("id", user.id).single().execute()
        user_name = profile.data.get("full_name", "User")
        user_profile_pic = profile.data.get("profile_url")

        query = supabase.table("Reports").select("*").eq("id", report_id)
        if profile.data.get("role") != "admin":
            query = query.eq("user_id", user.id)

        report_res = query.maybe_single().execute()
        if not report_res.data:
            return RedirectResponse(url="/reports")

        report = report_res.data
        formatted_date = format_iso_date(report.get("created_at", ""))

        prediction = report.get("career_prediction", "Software Engineering")
        top_recommendations = [career.strip() for career in prediction.split(",") if career.strip()][:3]
        if not top_recommendations:
            top_recommendations = ["Software Engineering"]

        primary_prediction = top_recommendations[0]

        # Parse matching factors and choose the first-career points for concise one-page preview
        matching_factor_raw = parse_json_maybe(report.get("matching_factor"), [])
        if isinstance(matching_factor_raw, list) and matching_factor_raw and isinstance(matching_factor_raw[0], list):
            matching_points = [str(x) for x in matching_factor_raw[0] if x]
        elif isinstance(matching_factor_raw, list):
            matching_points = [str(x) for x in matching_factor_raw if x]
        else:
            matching_points = []

        # Parse roadmap and choose phases for primary/top recommendation
        roadmap_raw = parse_json_maybe(report.get("roadmap"), [])
        roadmap_phases = []
        if isinstance(roadmap_raw, list):
            for rm in roadmap_raw:
                if not isinstance(rm, dict):
                    continue
                career_name = str(rm.get("career", "")).strip().lower()
                if career_name == primary_prediction.strip().lower():
                    phases = rm.get("phases", [])
                    roadmap_phases = phases if isinstance(phases, list) else []
                    break
            if not roadmap_phases and roadmap_raw and isinstance(roadmap_raw[0], dict):
                phases = roadmap_raw[0].get("phases", [])
                roadmap_phases = phases if isinstance(phases, list) else []

        # Fetch courses for primary recommendation only
        nepal_courses = []
        global_courses = []
        courses_res = supabase.table("Courses_DB").select("*").ilike("career_category", f"%{primary_prediction}%").execute()
        if courses_res.data:
            for c in courses_res.data:
                ctype = str(c.get("college_type", "local")).lower()
                if ctype == "local":
                    nepal_courses.append(c)
                else:
                    global_courses.append(c)

        return templates.TemplateResponse("report_pdf_preview.html", {
            "request": request,
            "report": report,
            "user_name": user_name,
            "user_profile_pic": user_profile_pic,
            "formatted_date": formatted_date,
            "primary_prediction": primary_prediction,
            "top_recommendations": top_recommendations,
            "matching_points": matching_points,
            "roadmap_phases": roadmap_phases,
            "nepal_courses": nepal_courses,
            "global_courses": global_courses
        })
    except HTTPException as he:
        raise he
    except Exception as e:
        print(f"Error loading report pdf preview data: {e}")
        raise HTTPException(status_code=500, detail="Failed to load report pdf preview.")

@router.delete("/reports/{report_id}")
async def delete_report(request: Request, report_id: str):
    access_token = request.cookies.get("access_token")
    if not access_token:
        raise HTTPException(status_code=401, detail="Unauthorized")

    try:
        user_response = supabase.auth.get_user(access_token)
        user = user_response.user
    except Exception:
        raise HTTPException(status_code=401, detail="Unauthorized")

    try:
        report_id_val = int(report_id)
        # Use authenticated client for RLS
        auth_client = create_client(
            url, key,
            options=ClientOptions(headers={"Authorization": f"Bearer {access_token}"})
        )
        res = auth_client.table("Reports").delete().eq("id", report_id_val).eq("user_id", user.id).execute()

        if not res.data:
            raise HTTPException(status_code=404, detail="Report not found or permission denied")

        return {"status": "success"}
    except HTTPException:
        raise
    except Exception as e:
        print(f"Delete report error: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete report")




@router.post("/reports/{report_id}/roadmap-progress")
async def update_roadmap_progress(request: Request, report_id: str):
    access_token = request.cookies.get("access_token")
    if not access_token:
        raise HTTPException(status_code=401, detail="Unauthorized")

    try:
        user_response = supabase.auth.get_user(access_token)
        user = user_response.user
    except Exception:
        raise HTTPException(status_code=401, detail="Unauthorized")

    try:
        body = await request.json()
        new_roadmap = body.get("roadmap")
        if not new_roadmap:
            raise HTTPException(status_code=400, detail="Missing roadmap data")

        report_id_val = int(report_id)

        # Use authenticated client so RLS allows the UPDATE
        auth_client = create_client(
            url, key,
            options=ClientOptions(headers={"Authorization": f"Bearer {access_token}"})
        )
        res = auth_client.table("Reports").update({"roadmap": new_roadmap}).eq("id", report_id_val).eq("user_id", user.id).execute()

        if not res.data:
            raise HTTPException(status_code=404, detail="Report not found")

        return {"status": "success"}
    except HTTPException:
        raise
    except Exception as e:
        print(f"Roadmap update error: {e}")
        raise HTTPException(status_code=500, detail="Failed to update progress")
