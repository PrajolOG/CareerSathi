from fastapi import APIRouter

router = APIRouter(prefix="/admin", tags=["Admin Dashboard"])

@router.get("/dashboard")
def admin_dashboard():
    return {"stats": {"total_users": 100, "active_sessions": 5}}

@router.get("/users")
def get_all_users():
    # Logic: Admin viewing all students
    return [
        {"id": 1, "name": "Ram", "role": "student"},
        {"id": 2, "name": "Sita", "role": "student"}
    ]
