from fastapi import APIRouter, Request, status, Form, UploadFile, File
from starlette.responses import RedirectResponse, HTMLResponse
from starlette.templating import Jinja2Templates
from sqladmin import Admin
from app.admin import admin_instance
import httpx
import os
import sqladmin
from app.config import settings

templates = Jinja2Templates(
    directory=[
        "app/templates",  # твои шаблоны
        os.path.join(os.path.dirname(sqladmin.__file__), "templates")
    ]
)

router = APIRouter()

@router.get("/admin/movies/new", response_class=HTMLResponse)
async def show_form(request: Request):
    from app.admin import admin_instance  # <-- важно импортировать здесь, чтобы подгрузился после setup_admin
    return templates.TemplateResponse("admin/movie_upload_form.html", {
        "request": request,
        "admin": admin_instance  # ← обязательно!
    })

@router.post("/admin/movies/new")
async def handle_upload(request: Request, title: str = Form(...), file: UploadFile = File(...)):
    files = {
        "title": (None, title),
        "file": (file.filename, await file.read(), file.content_type),
    }

    async with httpx.AsyncClient() as client:
        url = f"{settings.BACKEND_URL}/admin/upload_video"
        response = await client.post(url, files=files)

    if response.status_code != 200:
        return HTMLResponse(f"<h3>Ошибка загрузки: {response.text}</h3>", status_code=400)

    return RedirectResponse("/admin/movie/list", status_code=status.HTTP_302_FOUND)
