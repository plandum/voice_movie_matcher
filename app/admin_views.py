from sqladmin import ModelView
from app.models import User, Movie


class UserAdmin(ModelView, model=User):
    column_list = [User.id, User.email, User.created_at]
    name = "User"
    name_plural = "Users"
    icon = "fa-solid fa-user"


class MovieAdmin(ModelView, model=Movie):
    column_list = [Movie.id, Movie.title, Movie.duration, Movie.created_at]
    name = "Movie"
    name_plural = "Movies"
    icon = "fa-solid fa-film"
