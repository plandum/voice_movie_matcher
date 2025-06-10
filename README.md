# Voice Movie Matcher

Проект предоставляет API для сопоставления видеороликов с фильмами по звуковой дорожке и содержит
небольшую административную панель для загрузки фильмов и аудиодорожек.

## Установка

1. Клонируйте репозиторий и перейдите в его каталог.
2. Установите зависимости:
   ```bash
   pip install -r requirements.txt
   ```

## Настройка `.env`
Создайте файл `.env` в корне проекта и укажите параметры подключения к базе данных MySQL:

```env
DB_HOST=localhost
DB_PORT=3306
DB_USER=root
DB_PASSWORD=root
DB_NAME=voice_matcher
BACKEND_URL=http://127.0.0.1:8000
```

## Подготовка базы данных
Создайте базу данных `voice_matcher` в MySQL и выполните команду для создания таблиц:

```bash
python create_tables.py
```

## Запуск сервера

```bash
uvicorn app.main:app --reload
```

Приложение будет доступно по адресу `http://127.0.0.1:8000`.

## Основные эндпоинты

### Регистрация пользователя
`POST /auth/register`

```bash
curl -X POST http://127.0.0.1:8000/auth/register \
     -H 'Content-Type: application/json' \
     -d '{"email": "user@example.com", "password": "secret"}'
```

### Авторизация
`POST /auth/login`

```bash
curl -X POST http://127.0.0.1:8000/auth/login \
     -H 'Content-Type: application/x-www-form-urlencoded' \
     -d 'username=user@example.com&password=secret'
```

Ответ содержит поле `access_token`, которое используется в заголовке `Authorization`:
`Authorization: Bearer <TOKEN>`.

### Информация о текущем пользователе
`GET /auth/me`

```bash
curl http://127.0.0.1:8000/auth/me \
     -H 'Authorization: Bearer <TOKEN>'
```

### Сопоставление видеофрагмента
`POST /match/audio`

```bash
curl -X POST http://127.0.0.1:8000/match/audio \
     -F 'file=@fragment.mp4'
```

### Загрузка фильма (администрирование)
`POST /admin/upload_video`

```bash
curl -X POST http://127.0.0.1:8000/admin/upload_video \
     -F 'title=Example Movie' \
     -F 'file=@movie.mp4'
```

Эндпоинт сохраняет фильм, извлекает аудиодорожку и генерирует отпечатки для дальнейшего поиска.

## Дополнительно
Административная панель доступна по `/admin` и используется библиотеку `sqladmin`.

