from sqladmin import ModelView
from app.models import Genre

class GenreAdmin(ModelView, model=Genre):
    column_list = [Genre.id, Genre.name]
    form_columns = [Genre.name]
    name = "Жанр"
    name_plural = "Жанры"
    icon = "fa-solid fa-masks-theater"
