# 📱 Phone Login API

REST API для регистрации и авторизации пользователей по номеру телефона с подтверждением через SMS-код и встроенной реферальной системой.

![Django](https://img.shields.io/badge/Django-6.1-green)
![DRF](https://img.shields.io/badge/DRF-3.15-blue)
![Python](https://img.shields.io/badge/Python-3.14-yellow)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15-blue)
![License](https://img.shields.io/badge/license-MIT-lightgrey)

---

## 📋 Содержание

- [Возможности](#-возможности)
- [Технологии](#-технологии)
- [Установка](#-установка)
- [Запуск в Docker](#-запуск-в-docker)
- [API Endpoints](#-api-endpoints)
- [Примеры использования](#-примеры-использования)
- [Модели данных](#-модели-данных)
- [Документация](#-документация)
- [Безопасность](#-безопасность)

---

## ✨ Возможности

- ✅ Регистрация и авторизация по номеру телефона через SMS-код (без пароля)
- ✅ Автоматическая генерация уникального инвайт-кода для каждого пользователя
- ✅ Реферальная система: пользователь может активировать инвайт-код друга (один раз)
- ✅ JWT-аутентификация (access + refresh токены)
- ✅ Автоматическая OpenAPI 3.0 документация (ReDoc + Swagger UI)
- ✅ Rate limiting для защиты от флуда
- ✅ Template Views для серверного рендеринга (альтернатива API)

---

## 🛠 Технологии

| Стек | Технология |
|------|------------|
| Backend | Django 6.1, Django REST Framework |
| Аутентификация | djangorestframework-simplejwt |
| Документация | drf-spectacular (OpenAPI 3.0) |
| База данных | PostgreSQL 15 |
| Управление зависимостями | Poetry (`poetry.lock`) + `requirements.txt` |
| Python | 3.14 |

---

## 🚀 Установка

### 1. Клонирование и установка зависимостей

```bash
git clone https://github.com/serg-asabaev/phone_login.git
cd PhoneLogin
```

Создайте виртуальное окружение и установите зависимости:

```bash
python -m venv .venv

# Windows
.venv\Scripts\activate

# Linux / macOS
# source .venv/bin/activate

pip install -r requirements.txt
```

`requirements.txt` содержит все зависимости с зафиксированными версиями, перенесёнными из `poetry.lock`.
Достаточно этой команды — `poetry install` и `poetry init` не требуются.

> Если зависимости менялись в `poetry.lock`, обновите `requirements.txt`:
>
> ```bash
> python -c "import tomllib; d=tomllib.load(open('poetry.lock','rb')); p=d['package']; open('requirements.txt','w',encoding='utf-8',newline='\n').write('# Сгенерировано из poetry.lock — не редактировать вручную\n'+'\n'.join(n['name']+'=='+n['version']+(('; '+n['markers']) if n.get('markers') else '') for n in p)+'\n')"
> ```

### 2. Настройка окружения

Создайте файл `.env` в корне проекта:

```env
DEBUG=True
SECRET_KEY=your-secret-key-here

POSTGRES_DB=phone_login
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your_password
DB_HOST=localhost
DB_PORT=5432
```

### 3. Применение миграций и запуск

```bash
python manage.py makemigrations
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Сервер доступен по адресу: **http://127.0.0.1:8000/**

---

## 🐳 Запуск в Docker

Проект поднимается двумя контейнерами: `web` (Django + gunicorn) и `db` (PostgreSQL 15).
Миграции применяются автоматически при старте контейнера `web`.

### 1. Файл окружения

В корне проекта должен быть `.env` со следующими переменными
(значения `DB_HOST`/`DB_PORT` внутри Docker переопределяются на `db`/`5432` автоматически):

```env
DEBUG=True
SECRET_KEY=your-secret-key-here

POSTGRES_DB=phone_login
POSTGRES_USER=postgres
POSTGRES_PASSWORD=admin
DB_HOST=localhost
DB_PORT=5432
```

### 2. Сборка и запуск

```bash
docker compose up -d --build
```

Приложение будет доступно по адресу: **http://127.0.0.1:8000/**
(например, Swagger UI — http://127.0.0.1:8000/api/schema/swagger-ui/)

### 3. Полезные команды

```bash
# логи
docker compose logs -f web

# создать суперпользователя
docker compose exec web python manage.py createsuperuser

# выполнить команду управления
docker compose exec web python manage.py <команда>

# остановить
docker compose stop

# остановить и удалить контейнеры (данные БД в volume сохранятся)
docker compose down

# остановить и удалить контейнеры вместе с данными БД
docker compose down -v
```

### Файлы конфигурации

| Файл | Назначение |
|------|------------|
| `Dockerfile` | образ приложения (Python 3.14, зависимости из `requirements.txt`, gunicorn, запуск от непривилегированного пользователя) |
| `docker-compose.yml` | сервисы `web` + `db`, volume для данных PostgreSQL, healthcheck |
| `entrypoint.sh` | ожидание БД → `migrate` → запуск gunicorn |
| `.dockerignore` | исключения из build-контекста |
| `requirements.txt` | зависимости с зафиксированными версиями (перенесены из `poetry.lock`) — используются и в образе, и при локальной установке |

> Зависимости фиксируются в `poetry.lock`, а `requirements.txt` обновляется из него — см. раздел [Установка](#-установка).

---

## 🌐 API Endpoints

**Базовый URL:** `http://localhost:8000/users/auth/phone/`

| Метод | Endpoint | Описание | Auth |
|-------|----------|----------|------|
| `POST` | `/request-code/` | Запрос SMS-кода | ❌ |
| `POST` | `/verify-code/` | Подтверждение кода и вход | ❌ |
| `GET` | `/me/` | Получить профиль | ✅ |
| `POST` | `/apply-invite/` | Активировать инвайт-код | ✅ |
| `GET` | `/my-invited-users/` | Список приглашённых | ✅ |

---

## 📝 Примеры использования

### 1. Запрос SMS-кода

```bash
curl -X POST http://localhost:8000/users/auth/phone/request-code/ \
  -H "Content-Type: application/json" \
  -d '{"phone": "+79991234567"}'
```

**Ответ (200 OK):**
```json
{
  "message": "Код отправлен на номер телефона",
  "debug_code": "A3K9M2",
  "expires_in": 300
}
```

> ⚠️ Поле `debug_code` возвращается только в режиме `DEBUG=True`.

---

### 2. Подтверждение кода и вход

```bash
curl -X POST http://localhost:8000/users/auth/phone/verify-code/ \
  -H "Content-Type: application/json" \
  -d '{"phone": "+79991234567", "code": "A3K9M2"}'
```

**Ответ (200 OK):**
```json
{
  "message": "Регистрация успешна",
  "access": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "refresh": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "user": {
    "id": 1,
    "phone": "+79991234567",
    "invite_code": "X7Y2Z9",
    "invited_by": null,
    "has_used_invite": false,
    "is_active": true,
    "date_joined": "2026-10-16T10:00:00Z"
  },
  "is_new_user": true
}
```

---

### 3. Получить профиль

```bash
curl -X GET http://localhost:8000/users/auth/phone/me/ \
  -H "Authorization: Bearer <access_token>"
```

**Ответ (200 OK):**
```json
{
  "id": 1,
  "phone": "+79991234567",
  "invite_code": "X7Y2Z9",
  "invited_by": {
    "id": 5,
    "phone": "+79995555555"
  },
  "has_used_invite": true,
  "is_active": true,
  "date_joined": "2026-10-16T10:00:00Z"
}
```

---

### 4. Активировать инвайт-код

```bash
curl -X POST http://localhost:8000/users/auth/phone/apply-invite/ \
  -H "Authorization: Bearer <access_token>" \
  -H "Content-Type: application/json" \
  -d '{"invite_code": "X7Y2Z9"}'
```

**Ответ (200 OK):**
```json
{
  "message": "Инвайт-код успешно активирован",
  "invited_by": {
    "id": 5,
    "phone": "+79995555555"
  },
  "has_used_invite": true
}
```

**Ошибки (400 Bad Request):**
```json
{"invite_code": ["Вы уже активировали инвайт-код."]}
{"invite_code": ["Инвайт-код не найден"]}
{"invite_code": ["Нельзя использовать свой собственный инвайт-код"]}
```

---

### 5. Список приглашённых пользователей

```bash
curl -X GET http://localhost:8000/users/auth/phone/my-invited-users/ \
  -H "Authorization: Bearer <access_token>"
```

**Ответ (200 OK):**
```json
{
  "count": 2,
  "users": [
    {
      "id": 2,
      "phone": "+79992222222",
      "invite_code": "ABC123",
      "invited_by": {"id": 1, "phone": "+79991234567"},
      "has_used_invite": true,
      "is_active": true,
      "date_joined": "2026-10-16T11:00:00Z"
    }
  ]
}
```

---

## 🗄 Модели данных

### CustomUser

| Поле | Тип | Описание |
|------|-----|----------|
| `id` | int | Уникальный идентификатор |
| `phone` | string (unique) | Номер телефона (E.164) |
| `invite_code` | string (unique) | 6-значный инвайт-код |
| `invited_by` | FK → self | Кто пригласил (nullable) |
| `is_staff` | bool | Доступ к админке |
| `is_active` | bool | Активен ли пользователь |
| `date_joined` | datetime | Дата регистрации |

### SMSCode

| Поле | Тип | Описание |
|------|-----|----------|
| `id` | int | Уникальный идентификатор |
| `phone` | string | Номер телефона |
| `code` | string (6) | 6-значный код |
| `created_at` | datetime | Время создания |
| `expires_at` | datetime | Время истечения |
| `is_used` | bool | Использован ли код |

---

## 📖 Документация

После запуска сервера доступны:

| Интерфейс | URL                                          |
|-----------|----------------------------------------------|
| **ReDoc** | http://127.0.0.1:8000/api/schema/redoc/      |
| **Swagger UI** | http://127.0.0.1:8000/api/schema/swagger-ui/ |
| **OpenAPI схема** | http://127.0.0.1:8000/api/schema/            |

### Авторизация в Swagger UI

1. Получите access-токен через `/verify-code/`
2. Нажмите кнопку **Authorize** 🔓
3. Введите: `Bearer <ваш_токен>`
4. Готово — все защищённые эндпоинты доступны для тестирования

---

## 🔐 Безопасность

| Мера | Описание |
|------|----------|
| **Rate Limiting** | 10 запросов/минуту с одного IP |
| **Время жизни кода** | 5 минут |
| **Одноразовость** | Код удаляется после использования |
| **Криптостойкость** | Генерация через `secrets.choice()` |
| **JWT** | Access токен — 60 мин, Refresh — 7 дней |
| **Формат кода** | Исключены похожие символы (`0/O/1/I/l`) |

---

## 🔄 Поток работы

```
┌──────────────────┐
│ 1. Ввод телефона │
└────────┬─────────┘
         │ POST /request-code/
         ▼
┌──────────────────┐
│ 2. Получение SMS │
│    (6-значный    │
│     код)         │
└────────┬─────────┘
         │ POST /verify-code/
         ▼
┌──────────────────┐
│ 3. Получение JWT │
│  access + refresh│
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ 4. Профиль +     │
│  инвайт-код      │
└──────────────────┘
```

---

## ❌ HTTP-коды ответов

| Код | Описание |
|-----|----------|
| `200` | Успех |
| `201` | Ресурс создан |
| `400` | Ошибка валидации |
| `401` | Не авторизован |
| `403` | Доступ запрещён |
| `404` | Не найдено |
| `429` | Rate limit |
| `500` | Ошибка сервера |

---

## 📄 Лицензия

MIT

---

## 👨‍💻 Автор

Проект создан в рамках изучения Django REST Framework.

**Дата:** Октябрь 2026
```

Этот README можно сохранить в файл `README.md` в корне проекта — он готов к использованию на GitHub/GitLab и будет корректно отображаться с форматированием, таблицами и блоками кода.