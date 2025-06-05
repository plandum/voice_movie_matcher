from sqladmin.authentication import AuthenticationBackend
from starlette.requests import Request
from starlette.responses import RedirectResponse
from starlette.templating import Jinja2Templates
from starlette.responses import HTMLResponse

from app.database import SessionLocal
from app.models import User
from app.utils.security import verify_password
from app.utils.auth import create_access_token, verify_token

templates = Jinja2Templates(directory="app/templates")


class AdminAuth(AuthenticationBackend):
    async def login(self, request: Request) -> bool:
        form = await request.form()
        email = form.get("username")
        password = form.get("password")

        db = SessionLocal()
        user = db.query(User).filter(User.email == email).first()
        db.close()

        if not user or not verify_password(password, user.hashed_password):
            return False

        token = create_access_token({"sub": user.email})
        request.session.update({"token": token})
        return True

    async def logout(self, request: Request) -> bool:
        request.session.clear()
        return True

    async def authenticate(self, request: Request) -> bool:
        token = request.session.get("token")
        if not token:
            return False

        try:
            verify_token(token)
            return True
        except Exception:
            return False
