from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session

from app import models, schemas
from app.database import SessionLocal
from app.utils.security import hash_password
from fastapi.security import OAuth2PasswordRequestForm
from app.utils.auth import verify_password, create_access_token, get_current_user

router = APIRouter(prefix="/auth", tags=["auth"])

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.post("/register", response_model=schemas.UserResponse)
def register_user(user: schemas.UserCreate, db: Session = Depends(get_db)):
    # Проверка на существующего пользователя
    existing_user = db.query(models.User).filter(models.User.email == user.email).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Пользователь с таким email уже существует")

    # Хеширование пароля и сохранение
    hashed = hash_password(user.password)
    db_user = models.User(email=user.email, hashed_password=hashed)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)

    return schemas.UserResponse.from_orm_with_status(db_user)

@router.post("/login", response_model=schemas.Token)
def auth_user(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == form_data.username).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Неверный email или пароль")

    token = create_access_token(data={"sub": user.email})
    return {"access_token": token, "token_type": "bearer"}



@router.get("/me", response_model=schemas.UserResponse)
def read_current_user(current_user: models.User = Depends(get_current_user)):
    return current_user
