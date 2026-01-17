# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Travellito is a tour booking platform with Telegram integration, consisting of three main services:
- **Web API**: FastAPI backend with PostgreSQL
- **Bot**: Telegram bot for tourists (aiogram 3.4)
- **WebApp**: React SPA embedded in Telegram (Vite + TypeScript + TailwindCSS)

## Architecture

### Multi-Service Structure

```
travellito/
├── web/              # FastAPI backend (port 8000)
│   ├── app/
│   │   ├── api/v1/   # API endpoints (clean architecture)
│   │   ├── services/ # Business logic layer
│   │   ├── models.py # SQLAlchemy models
│   │   └── security.py # JWT auth, role-based access
│   ├── alembic/      # Database migrations
│   ├── static/       # Static assets for admin panel
│   └── templates/    # Jinja2 templates
├── bot/              # Telegram bot (port 8080)
│   ├── app/
│   │   ├── main.py   # Tourist bot
│   │   └── support_bot.py # Support bot (port 8081)
│   └── webapp/       # React SPA for Telegram WebApp
│       └── src/
│           ├── pages/    # App, TourDetail, Checkout, MyBookings
│           ├── auth.ts   # Telegram WebApp auth
│           └── api/      # API client
└── docker-compose.yml
```

### Database Models (web/app/models.py)

Key entities:
- **User**: role (admin, agency, landlord, manager, bot_user)
- **Tour**: created by agencies, has departures and ticket categories
- **Departure**: specific tour date with capacity/pricing
- **Purchase**: bookings with items (tickets)
- **Referral**: landlord QR code scans for commission tracking
- **SupportMessage/SupportResponse**: customer support system
- **LandlordPaymentRequest/History**: commission payment tracking

### Authentication Flow

**Telegram WebApp → Backend**:
1. Frontend gets `initData` from Telegram WebApp SDK
2. POST to `/api/v1/auth/telegram/init` with initData
3. Backend verifies HMAC signature using BOT_TOKEN
4. Issues JWT tokens in HttpOnly, Secure, SameSite=None cookies
5. Access token (15 min), Refresh token (14 days)

See README.md for full authentication details.

### API Architecture (Clean Architecture)

**Endpoints** (web/app/api/v1/endpoints/):
- `auth.py` - Login, logout, refresh, Telegram WebApp auth
- `public.py` - Tour search, tour details, cities, categories (no auth)
- `tours.py` - Agency tour management
- `bookings.py` - Purchase management
- `admin.py` - Platform metrics, user management, API keys
- `landlord.py` - Apartments, QR codes, earnings
- `support.py` - Support message handling

**Services** (web/app/services/):
- Business logic layer (e.g., `tour_service.py`, `booking_service.py`)
- Called by endpoints, use SQLAlchemy sessions directly
- Handle domain logic, validations, external integrations

**Schemas** (web/app/api/v1/schemas/):
- Pydantic models for request/response validation

## Development Commands

### Web Backend

```bash
# Run web service
cd web
uvicorn app.main:app --reload --host=0.0.0.0 --port=8000

# Database migrations
cd web
alembic upgrade head              # Apply migrations
alembic revision --autogenerate -m "description"  # Create migration

# Docker
docker-compose up web
docker-compose exec web alembic upgrade head
```

### Telegram Bot

```bash
# Run tourist bot
cd bot
uvicorn app.main:app --reload --host=0.0.0.0 --port=8080

# Run support bot
cd bot
uvicorn app.support_bot:app --reload --host=0.0.0.0 --port=8081

# Docker
docker-compose up bot support-bot
```

### WebApp (React)

```bash
# Development server
cd bot/webapp
npm install
npm run dev        # Vite dev server on port 5173

# Production build
npm run build      # Outputs to bot/webapp/dist
npm run preview    # Preview production build
```

### Full Stack

```bash
# Start all services
docker-compose up

# Build with version
APP_VERSION=1.0.0 docker-compose build
```

## Role-Based Access Control

**Roles** (web/app/roles.py):
- `admin` - Platform administrators (metrics, user management, settings)
- `agency` - Tour operators (create tours, manage bookings)
- `manager` - Agency employees (limited agency access)
- `landlord` - Property owners (apartments, referral QR codes, earnings)
- `bot_user` - Telegram bot users (book tours via WebApp)
- `bot` - Bot service account

**Usage in endpoints**:
```python
from app.security import role_required, current_user

@router.get("/admin-only")
async def admin_route(user: Annotated[User, Depends(role_required("admin"))]):
    ...
```

## Key Technologies

**Backend**:
- FastAPI 0.111 + Uvicorn (ASGI)
- SQLAlchemy 2.0 (async) + asyncpg
- aiogram 3.4 (Telegram bot framework)
- python-jose (JWT signing)
- Alembic (migrations)
- Minio (S3-compatible object storage)
- Redis (rate limiting via slowapi)

**Frontend**:
- React 18 + TypeScript
- Vite 4 (build tool)
- TailwindCSS + tailwindcss-animate
- React Router 6
- TanStack Query (react-query)
- axios (HTTP client)
- Telegram WebApp SDK

**Infrastructure**:
- PostgreSQL 15
- Docker Compose
- Yandex Metrica (analytics - see YANDEX_METRICA_INTEGRATION.md)

## Important Patterns

### Timezone Handling
- Use `pytz` for timezone conversions (see models.py for Purchase.created_at_msk)
- Database stores UTC, display in Moscow time (Europe/Moscow)

### Telegram WebApp Integration
- Load SDK: `<script src="https://telegram.org/js/telegram-web-app.js"></script>`
- Signal ready: `window.Telegram.WebApp.ready()`
- Get initData: `window.Telegram.WebApp.initData`
- Auth via `/api/v1/auth/telegram/init` endpoint

### S3 Storage (Minio)
- Configured via `web/app/storage.py`
- Used for tour images, landlord QR codes
- Environment: S3_ENDPOINT, S3_ACCESS_KEY, S3_SECRET_KEY, S3_BUCKET

### Token Refresh
- Middleware auto-refreshes expired access tokens (web/app/api/v1/middleware.py)
- Frontend interceptor handles 401 responses (bot/webapp/src/auth.ts)
- See web/README.md for detailed token refresh flow

### Support System
- Tourist bot triggers admin notifications via support bot
- Landlords request payments (min 10 engaged users)
- See SUPPORT_BOT_GUIDE.md for full details

## Environment Variables

Key variables (see .env, docker-compose.yml):
- `BOT_TOKEN` - Telegram bot token
- `SUPPORT_BOT_TOKEN` - Support bot token
- `DB_DSN` - PostgreSQL connection string
- `SECRET_KEY` - JWT signing key
- `WEBAPP_URL` - WebApp URL for bot
- `WEB_API` - Backend API URL for bot
- `S3_*` - Object storage config
- `METRIKA_COUNTER`, `METRIKA_MP_TOKEN` - Analytics

## Testing Notes

- Token refresh test page: `/token-refresh-test`
- Healthcheck endpoints: `/healthz` (all services)
- API docs: `http://localhost:8000/docs` (Swagger UI)
