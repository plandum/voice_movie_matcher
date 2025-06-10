from fastapi import FastAPI
from starlette.middleware.sessions import SessionMiddleware

from app.database import engine
from app.admin import setup_admin
from app.routes import admin as admin_routes
from app.routes import auth, match  # если есть match
from app.routes import custom_admin

from fastapi.staticfiles import StaticFiles

app = FastAPI(title="Voice Over API")

app.add_middleware(SessionMiddleware, secret_key="abc-qwerty-key")

app.mount("/media", StaticFiles(directory="media"), name="media")

# Подключение роутов
app.include_router(auth.router)
app.include_router(admin_routes.router)
app.include_router(match.router)
app.include_router(custom_admin.router)

# Админка
setup_admin(app, engine)
