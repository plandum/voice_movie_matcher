from fastapi import APIRouter, Request, status, Form, UploadFile, File
from starlette.responses import RedirectResponse, HTMLResponse
from starlette.templating import Jinja2Templates
from sqladmin import Admin
from app.admin import admin_instance
import httpx
import os
import sqladmin
from app.config import settings

templates = Jinja2Templates(
    directory=[
        "app/templates",  # твои шаблоны
        os.path.join(os.path.dirname(sqladmin.__file__), "templates")
    ]
)

router = APIRouter()

@router.get("/admin/movies/new", response_class=HTMLResponse)
async def show_form(request: Request):
    from app.admin import admin_instance  # <-- важно импортировать здесь, чтобы подгрузился после setup_admin
    return templates.TemplateResponse("admin/movie_upload_form.html", {
        "request": request,
        "admin": admin_instance  # ← обязательно!
    })

@router.post("/admin/movies/new")
async def handle_upload(request: Request, title: str = Form(...), file: UploadFile = File(...)):
    files = {
        "title": (None, title),
        "file": (file.filename, await file.read(), file.content_type),
    }

    async with httpx.AsyncClient() as client:
        url = f"{settings.BACKEND_URL}/admin/upload_video"
        response = await client.post(url, files=files)

    if response.status_code != 200:
        return HTMLResponse(f"<h3>Ошибка загрузки: {response.text}</h3>", status_code=400)

    return RedirectResponse("/admin/movie/list", status_code=status.HTTP_302_FOUND)

@router.get("/admin/audio-track/new", response_class=HTMLResponse)
async def show_audio_track_form(request: Request):
    from app.models import Movie
    from app.database import SessionLocal
    from app.admin import admin_instance  # <-- важно импортировать здесь, чтобы подгрузился после setup_admin

    db = SessionLocal()
    movies = db.query(Movie).order_by(Movie.title).all()
    db.close()

    return templates.TemplateResponse("admin/upload_track.html", {
        "request": request,
        "admin": admin_instance,  # ← критично для шаблона sqladmin/layout.html
        "movies": movies
    })


@router.post("/admin/audio-track/new")
async def handle_audio_track_upload(
    request: Request,
    movie_id: int = Form(...),
    language: str = Form("unknown"),
    file: UploadFile = File(...)
):
    from app.database import SessionLocal
    from app.models import AudioTrack, AudioFingerprint
    from app.utils.peaks import extract_peaks
    import librosa
    import shutil
    import os
    from decimal import Decimal, ROUND_HALF_UP

    def round_time(t: float) -> float:
        return float(Decimal(str(t)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))

    MEDIA_DIR = "media/uploads"
    os.makedirs(MEDIA_DIR, exist_ok=True)

    path = os.path.join(MEDIA_DIR, file.filename)
    with open(path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    try:
        y, sr = librosa.load(path, sr=None)
        peaks = extract_peaks(y, sr)
    except Exception as e:
        return HTMLResponse(f"<h3>Ошибка анализа аудио: {e}</h3>", status_code=400)

    db = SessionLocal()
    try:
        track = AudioTrack(
            movie_id=movie_id,
            language=language,
            track_path=path
        )
        db.add(track)
        db.commit()
        db.refresh(track)

        for t in sorted(set(round_time(t) for t in peaks)):
            db.add(AudioFingerprint(audio_track_id=track.id, timestamp=t))

        db.commit()
    finally:
        db.close()

    return RedirectResponse("/admin/audio-track/list", status_code=status.HTTP_302_FOUND)


