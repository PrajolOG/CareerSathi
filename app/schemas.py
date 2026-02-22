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

# --- General Models ---
class UserResponse(BaseModel):
    id: str
    username: str
    email: EmailStr