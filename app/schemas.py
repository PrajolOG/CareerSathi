from pydantic import BaseModel, EmailStr
from typing import Optional

# --- Auth Models ---
class UserSignup(BaseModel):
    email: EmailStr
    password: str
    full_name: str
    grade_level: str
    gender: str

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class AuthResponse(BaseModel):
    message: str
    access_token: Optional[str] = None
    user_id: Optional[str] = None
    error: Optional[str] = None

# --- Chat Models ---
class ChatMessage(BaseModel):
    # Optional since we can often get this from the session/cookie
    user_id: Optional[str] = None  
    message: str

# --- Report Models ---
class GeneralInfo(BaseModel):
    gender: str
    city_type: str
    family_income: str
    plus2_stream: str
    plus2_gpa: float

class GradesInfo(BaseModel):
    english: str = ""
    nepali: str = ""
    social: str = ""
    math: str = ""
    physics: str = ""
    chemistry: str = ""
    biology: str = ""
    computer: str = ""
    accounts: str = ""
    economics: str = ""
    law: str = ""

class InterestsInfo(BaseModel):
    technology: int = 0
    math_stats: int = 0
    art_design: int = 0
    business_money: int = 0
    social_people: int = 0
    bio_health: int = 0
    nature_agri: int = 0
    construction: int = 0
    law_politics: int = 0
    hospitality_food: int = 0
    gaming_entertainment: int = 0
    history_culture: int = 0

class EntranceScoresInfo(BaseModel):
    ioe: int = 0
    cee: int = 0
    cmat: int = 0

class ReportGenerationRequest(BaseModel):
    general_info: GeneralInfo
    grades: GradesInfo
    interests: InterestsInfo
    entrance_scores: EntranceScoresInfo

# --- General Models ---
class UserResponse(BaseModel):
    id: str
    username: str
    email: EmailStr