from fastapi import FastAPI
from app.routes import admin
from app.routes import match

app = FastAPI(title="Movie Audio Matcher API")

app.include_router(admin.router)
app.include_router(match.router)
