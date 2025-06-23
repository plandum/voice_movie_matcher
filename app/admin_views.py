from sqladmin import ModelView
from app.models import User, Movie, Genre, Country, Actor, Director


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

class GenreAdmin(ModelView, model=Genre):
    column_list = [Genre.id, Genre.name]
    name = "Жанр"
    name_plural = "Жанры"
    icon = "fa-solid fa-masks-theater"

class CountryAdmin(ModelView, model=Country):
    column_list = [Country.id, Country.name]
    name = "Страна"
    name_plural = "Страны"
    icon = "fa-solid fa-earth-americas"

class ActorAdmin(ModelView, model=Actor):
    column_list = [Actor.id, Actor.name]
    name = "Актёр"
    name_plural = "Актёры"
    icon = "fa-solid fa-user"

class DirectorAdmin(ModelView, model=Director):
    column_list = [Director.id, Director.name]
    name = "Режиссёр"
    name_plural = "Режиссёры"
    icon = "fa-solid fa-clapperboard"
