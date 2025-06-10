from sqladmin import ModelView
from starlette.requests import Request
from starlette.responses import RedirectResponse, HTMLResponse
from fastapi import status
from starlette.templating import Jinja2Templates
from sqladmin import Admin
from app.models import Movie
import httpx
import os
import sqladmin

templates = Jinja2Templates(
    directory=[
        "app/templates",  # твои шаблоны
        os.path.join(os.path.dirname(sqladmin.__file__), "templates")
    ]
)


class MovieAdmin(ModelView, model=Movie):
    name = "Фильм"
    name_plural = "Фильмы"
    icon = "fa-solid fa-film"

    can_create = False
    can_edit = True
    can_delete = True

    add_template = "admin/movie_upload_form.html"
    list_template = "admin/movie_list.html"

    column_list = [
        Movie.id,
        Movie.title,
        Movie.duration,
        Movie.poster_url,
        Movie.created_at
    ]

    async def add(self, request: Request) -> HTMLResponse:
        context = {
            "request": request,
            "admin": self.admin,
        }
        return self.templates.TemplateResponse("admin/movie_upload_form.html", context)

    async def create(self, request: Request) -> RedirectResponse:
        """Этот метод вызывается при POST-запросе с формы создания"""
        form = await request.form()
        title = form.get("title")
        file = form.get("file")

        files = {
            "title": (None, title),
            "file": (file.filename, await file.read(), file.content_type),
        }

        async with httpx.AsyncClient() as client:
            response = await client.post("/admin/upload_video", files=files)

        if response.status_code != 200:
            return HTMLResponse(f"<h3>Ошибка загрузки: {response.text}</h3>", status_code=400)

        return RedirectResponse("/admin/movie/list", status_code=status.HTTP_302_FOUND)