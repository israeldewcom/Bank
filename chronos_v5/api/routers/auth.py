# chronos_v5/api/routers/auth.py
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, EmailStr
from typing import Optional
from chronos_v5.services.auth_service import AuthService
from chronos_v5.api.dependencies.auth_deps import get_current_user, get_tenant_from_request
from chronos_v5.models import User
from chronos_v5.logger_setup import logger

router = APIRouter()

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    full_name: str

class LoginRequest(BaseModel):
    email: EmailStr
    password: str
    device_fingerprint: Optional[str] = None

class PairRequest(BaseModel):
    email: EmailStr
    pairing_code: str
    device_name: str
    device_fingerprint: str

@router.post("/register")
def register(req: RegisterRequest, request: Request):
    tenant = get_tenant_from_request(request)
    service = AuthService()
    try:
        user = service.register_user(req.email, req.password, req.full_name, tenant)
        return {"status": "pending", "message": "Registration successful. Awaiting admin approval.", "user_id": str(user.id)}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/login")
def login(req: LoginRequest):
    service = AuthService()
    try:
        token = service.login(req.email, req.password, req.device_fingerprint)
        return {"access_token": token, "token_type": "bearer"}
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))

@router.post("/pairing-code")
def request_pairing_code(
    request: Request,
    device_name: str,
    current_user: User = Depends(get_current_user)  # <-- fixed dependency
):
    service = AuthService()
    code = service.create_pairing_code(current_user.id, device_name)
    return {"pairing_code": code, "expires_in": 300}

@router.post("/pair-device")
def pair_device(req: PairRequest):
    service = AuthService()
    try:
        device = service.pair_device(req.pairing_code, req.device_fingerprint)
        return {"status": "pending", "device_id": str(device.id), "message": "Device pending admin approval"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
