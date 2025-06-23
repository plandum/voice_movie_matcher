from sqladmin import ModelView
from app.models import Actor

class ActorAdmin(ModelView, model=Actor):
    column_list = [Actor.id, Actor.name]
    form_columns = [Actor.name]
    name = "Актёр"
    name_plural = "Актёры"
    icon = "fa-solid fa-user"
