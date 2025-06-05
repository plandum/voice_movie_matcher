# app/admin.py

from sqladmin import Admin
from app.admin_auth import AdminAuth
from app.models import Movie, User
from app.admin_views.movie_admin import MovieAdmin
from app.admin_views import UserAdmin

from jinja2 import ChoiceLoader, FileSystemLoader

admin_instance = None  # ← глобальная переменная

def setup_admin(app, engine):
    global admin_instance  # ← обязательно, чтобы изменить глобальную переменную

    authentication_backend = AdminAuth(secret_key="abc-qwerty-key")
    admin_instance = Admin(app=app, engine=engine, authentication_backend=authentication_backend)

    # Подключаем шаблоны
    extra_loader = FileSystemLoader("app/templates")
    admin_instance.templates.env.loader = ChoiceLoader([
        admin_instance.templates.env.loader,
        extra_loader
    ])

    # Добавляем views
    admin_instance.add_view(MovieAdmin)
    admin_instance.add_view(UserAdmin)
