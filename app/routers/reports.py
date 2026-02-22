from fastapi import APIRouter

# Tag is "Reports" so it shows up separately in documentation
router = APIRouter(tags=["Student Reports"])

@router.get("/reports")
def get_student_reports():
    # Logic: Fetch the career assessment report for the logged-in student
    return {
        "student_id": 1,
        "reports": [
            {
                "report_id": 101,
                "title": "Career Prediction Report",
                "date": "2023-10-27",
                "recommended_career": "Software Engineering",
                "score": "85%"
            },
        ]
    }