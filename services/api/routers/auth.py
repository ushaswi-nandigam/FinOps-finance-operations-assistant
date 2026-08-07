from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel
from sqlalchemy.orm import Session

from services.api.deps import get_db
from services.auth.security import authenticate, create_access_token, decode_access_token

router = APIRouter(prefix="/auth", tags=["auth"])
_bearer = HTTPBearer(auto_error=False)


class LoginRequest(BaseModel):
    username: str
    password: str


@router.post("/login")
def login(req: LoginRequest, db: Session = Depends(get_db)) -> dict:
    user = authenticate(db, username=req.username, password=req.password)
    if user is None:
        raise HTTPException(401, "invalid username or password")
    return {"access_token": create_access_token(user), "token_type": "bearer", **user}


def current_user(creds: HTTPAuthorizationCredentials | None = Depends(_bearer)) -> dict:
    if creds is None:
        raise HTTPException(401, "missing bearer token")
    payload = decode_access_token(creds.credentials)
    if payload is None:
        raise HTTPException(401, "invalid or expired token")
    return payload


@router.get("/me")
def me(user: dict = Depends(current_user)) -> dict:
    return user
