from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session

from app import models, schemas
from app.database import SessionLocal
from fastapi.security import OAuth2PasswordRequestForm
from app.utils.auth import create_access_token, get_current_user
from app.utils.email import send_verification_email

import random
from datetime import datetime, timedelta


router = APIRouter(prefix="/auth", tags=["auth"])

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.post("/register", response_model=schemas.UserResponse)
def send_code(user: schemas.UserEmail, db: Session = Depends(get_db)):
    code = f"{random.randint(0, 999999):06}"  # генерируем 6-значный код
    existing_user = db.query(models.User).filter(models.User.email == user.email).first()

    if existing_user:
        existing_user.verification_code = code
        existing_user.code_generated_at = datetime.utcnow()
    else:
        existing_user = models.User(
            email=user.email,
            verification_code=code,
            code_generated_at=datetime.utcnow()
        )
        db.add(existing_user)

    db.commit()

    send_verification_email(user.email, code)  # можно мокнуть пока

    return schemas.UserResponse.from_orm_with_status(existing_user)

@router.post("/login", response_model=schemas.Token)
def login_with_code(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == form_data.username).first()

    if not user:
        raise HTTPException(status_code=401, detail="Сначала запросите код")

    if user.verification_code != form_data.password:
        raise HTTPException(status_code=401, detail="Неверный код")

    if user.code_generated_at is None or (datetime.utcnow() - user.code_generated_at > timedelta(minutes=10)):
        raise HTTPException(status_code=400, detail="Код истёк")

    token = create_access_token(data={"sub": user.email})

    # Сбрасываем код после успешного входа
    user.verification_code = None
    user.code_generated_at = None
    db.commit()

    return {"access_token": token, "token_type": "bearer"}




@router.get("/me", response_model=schemas.UserResponse)
def read_current_user(current_user: models.User = Depends(get_current_user)):
    return current_user
