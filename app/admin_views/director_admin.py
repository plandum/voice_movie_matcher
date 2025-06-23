from sqladmin import ModelView
from app.models import Director

class DirectorAdmin(ModelView, model=Director):
    column_list = [Director.id, Director.name]
    form_columns = [Director.name]
    name = "Режиссёр"
    name_plural = "Режиссёры"
    icon = "fa-solid fa-clapperboard"
