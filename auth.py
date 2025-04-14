from datetime import datetime, timedelta, timezone
from typing import Optional
from passlib.context import CryptContext
from jose import JWTError, jwt
from sqlalchemy.orm import Session
from database import Admin
import os

# JWT configuration
SECRET_KEY = os.getenv("SECRET_KEY")  # In production, use a secure randomly generated key loaded from environment
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 hours

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

def authenticate_admin(db: Session, username: str, password: str):
    admin = db.query(Admin).filter(Admin.username == username).first()
    if not admin:
        return False
    if not verify_password(password, admin.password_hash):
        return False
    return admin

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def init_admin(db: Session):
    """Initialize a default admin if none exists"""
    admin_exists = db.query(Admin).filter(Admin.username == "admin").first()
    if not admin_exists:
        admin = Admin(
            username="admin", 
            password_hash=get_password_hash(os.getenv("ADMIN_PASSWORD"))
        )
        db.add(admin)
        db.commit()
        db.refresh(admin)
        return admin
    return admin_exists 