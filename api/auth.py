"""JWT creation/verification and password hashing."""

from datetime import datetime, timedelta
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session as DBSession

from config import settings
from database import get_db
from models_db import User

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


import hashlib

# If passlib has compatibility issues with newer bcrypt (e.g. Python 3.13 / bcrypt 4.x bug wrap test),
# fallback to hashlib sha256 or safe bcrypt
def hash_password(password: str) -> str:
    try:
        # truncate to 72 bytes if necessary for bcrypt
        pwd_bytes = password.encode("utf-8")[:72].decode("utf-8", errors="ignore")
        return pwd_context.hash(pwd_bytes)
    except Exception:
        # Fallback to sha256 hashing if passlib bcrypt backend fails
        return "sha256$" + hashlib.sha256(password.encode("utf-8")).hexdigest()


def verify_password(plain: str, hashed: str) -> bool:
    if hashed.startswith("sha256$"):
        return ("sha256$" + hashlib.sha256(plain.encode("utf-8")).hexdigest()) == hashed
    try:
        plain_bytes = plain.encode("utf-8")[:72].decode("utf-8", errors="ignore")
        return pwd_context.verify(plain_bytes, hashed)
    except Exception:
        return False


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (
        expires_delta or timedelta(minutes=settings.access_token_expire_minutes)
    )
    to_encode["exp"] = expire
    return jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: DBSession = Depends(get_db),
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(
            token, settings.secret_key, algorithms=[settings.algorithm]
        )
        email: str | None = payload.get("sub")
        if email is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = db.query(User).filter(User.email == email).first()
    if user is None or not user.is_active:
        raise credentials_exception
    return user


def require_clinician(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role not in ("clinician", "admin"):
        raise HTTPException(status_code=403, detail="Clinician access required")
    return current_user
