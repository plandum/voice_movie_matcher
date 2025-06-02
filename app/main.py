from fastapi import FastAPI
from app.routes import admin
from app.routes import match
from app.routes import auth

app = FastAPI(title="Voice Over API")

app.include_router(admin.router)
app.include_router(match.router)
app.include_router(auth.router)