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
    form_columns = [
        Movie.id,
        Movie.title,
        Movie.description,
        Movie.duration,
        Movie.directors,
        Movie.actors,
        Movie.countries,
        Movie.genres,
        Movie.poster_url,
        Movie.age_rating,
    ]


    async def add(self, request: Request) -> HTMLResponse:
        context = {
            "request": request,
            "admin": self.admin,
        }
        return self.templates.TemplateResponse("admin/movie_upload_form.html", context)

    async def create(self, request: Request) -> RedirectResponse:
        form = await request.form()

        data = {
            "title": form.get("title"),
            "description": form.get("description"),
            "age_rating": form.get("age_rating"),
            "genre_ids": form.getlist("genre_ids"),
            "country_ids": form.getlist("country_ids"),
            "actor_ids": form.getlist("actor_ids"),
            "director_ids": form.getlist("director_ids"),
        }

        files = []
        if form.get("poster"):
            poster = form.get("poster")
            files.append(
                ("poster", (poster.filename, await poster.read(), poster.content_type))
            )

        # передаём данные как multipart/form-data
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "http://127.0.0.1:8000/admin/movies/new",
                data=data,
                files=files
            )

        if response.status_code != 302:
            return HTMLResponse(f"<h3>Ошибка загрузки: {response.text}</h3>", status_code=400)

        return RedirectResponse("/admin/movie/list", status_code=status.HTTP_302_FOUND)
