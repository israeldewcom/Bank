from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.orm import Session
from chronos_v5.database import SyncSessionLocal
from chronos_v5.models import User
from chronos_v5.config import Config
from pydantic import BaseModel
from datetime import datetime, timedelta, timezone
import uuid, os

router = APIRouter(prefix="/admin", tags=["Admin"])

# --- Helper: Super Admin Auth (using the master API key for security) ---
def get_super_admin(api_key: str = Header(..., alias="X-API-Key")):
    if api_key != Config.API_KEY:
        raise HTTPException(status_code=403, detail="Invalid Master Key")
    return True

# --- Models for requests ---
class UserCreate(BaseModel):
    email: str
    password: str
    full_name: str
    trial_days: int = 7  # Default free trial

class UserUpdate(BaseModel):
    is_active: bool = None
    role: str = None
    trial_days: int = None  # extend trial

class LoginRequest(BaseModel):
    email: str
    password: str

# --- 1. LOGIN ---
@router.post("/login")
def login(data: LoginRequest):
    db = SyncSessionLocal()
    user = db.query(User).filter(User.email == data.email).first()
    db.close()
    if not user or not user.check_password(data.password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account deactivated. Contact admin.")
    if user.trial_expiry and datetime.now(timezone.utc) > user.trial_expiry:
        raise HTTPException(status_code=403, detail="Trial expired. Please upgrade.")
    
    # Update last login
    db = SyncSessionLocal()
    user.last_login = datetime.now(timezone.utc)
    db.commit()
    db.close()
    
    return {
        "status": "success", 
        "tenant": user.tenant, 
        "role": user.role,
        "name": user.full_name
    }

# --- 2. CREATE USER (Free Trial) ---
@router.post("/users", dependencies=[Depends(get_super_admin)])
def create_user(data: UserCreate):
    db = SyncSessionLocal()
    existing = db.query(User).filter(User.email == data.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already exists")
    
    user = User(
        id=str(uuid.uuid4()),
        email=data.email,
        full_name=data.full_name,
        tenant=data.email.split('@')[0],  # Auto-create tenant from email
        trial_expiry=datetime.now(timezone.utc) + timedelta(days=data.trial_days)
    )
    user.set_password(data.password)
    db.add(user)
    db.commit()
    db.refresh(user)
    db.close()
    return {"message": f"User created. Trial expires in {data.trial_days} days.", "user_id": user.id}

# --- 3. LIST ALL USERS (Monitoring) ---
@router.get("/users", dependencies=[Depends(get_super_admin)])
def list_users():
    db = SyncSessionLocal()
    users = db.query(User).all()
    db.close()
    return [{
        "id": u.id,
        "email": u.email,
        "tenant": u.tenant,
        "is_active": u.is_active,
        "trial_expiry": u.trial_expiry,
        "role": u.role,
        "last_login": u.last_login
    } for u in users]

# --- 4. TOGGLE USER (Remove/Deactivate) ---
@router.put("/users/{user_id}/status", dependencies=[Depends(get_super_admin)])
def toggle_user(user_id: str, data: UserUpdate):
    db = SyncSessionLocal()
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if data.is_active is not None:
        user.is_active = data.is_active
    if data.role is not None:
        user.role = data.role
    if data.trial_days:
        user.trial_expiry = datetime.now(timezone.utc) + timedelta(days=data.trial_days)
    
    db.commit()
    db.close()
    return {"message": f"User {user.email} updated."}

# --- 5. CHECK TRIAL STATUS (Called on every login) ---
# (used by login endpoint)
