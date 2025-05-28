from app.database import engine
from app.models import Base

print("Создание таблиц...")
Base.metadata.create_all(bind=engine)
print("Таблицы успешно созданы.")
