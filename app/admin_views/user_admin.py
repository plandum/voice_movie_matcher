from sqladmin import ModelView
from app.models import User

class UserAdmin(ModelView, model=User):
    column_list = [User.id, User.email, User.created_at]
    name = "Пользователь"
    name_plural = "Пользователи"
    icon = "fa-solid fa-user"
