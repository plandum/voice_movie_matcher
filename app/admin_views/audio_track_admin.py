from sqladmin import ModelView
from app.models import AudioTrack
from starlette.templating import Jinja2Templates
import os
import sqladmin

templates = Jinja2Templates(
    directory=[
        "app/templates",
        os.path.join(os.path.dirname(sqladmin.__file__), "templates")
    ]
)

class AudioTrackAdmin(ModelView, model=AudioTrack):
    name = "Аудиодорожка"
    name_plural = "Аудиодорожки"
    icon = "fa-solid fa-music"

    list_template = "admin/audio_track_list.html"

    can_create = False
    can_edit = True
    can_delete = True

    column_list = [
        AudioTrack.id,
        "movie",  # доступен через backref
        AudioTrack.language,
        AudioTrack.track_path,
        AudioTrack.created_at,
    ]

    column_searchable_list = [AudioTrack.language, AudioTrack.track_path]
    column_sortable_list = [AudioTrack.id, AudioTrack.created_at]

    column_labels = {
        "id": "ID",
        "movie": "Фильм",
        "language": "Язык",
        "track_path": "Путь к файлу",
        "created_at": "Дата загрузки"
    }
    
    form_columns = [
        "movie",
        "language",
        "track_path",
    ]