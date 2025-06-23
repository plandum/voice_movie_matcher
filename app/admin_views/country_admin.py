from sqladmin import ModelView
from app.models import Country

class CountryAdmin(ModelView, model=Country):
    column_list = [Country.id, Country.name]
    form_columns = [Country.name]
    name = "Страна"
    name_plural = "Страны"
    icon = "fa-solid fa-earth-americas"
