# Travellito API v1

This is the refactored API following clean architecture principles.

## Directory Structure

```
v1/
├── api.py              # Main API router configuration
├── middleware.py       # Exception handling middleware
├── endpoints/          # HTTP endpoint handlers (controllers)
│   ├── admin.py       # Admin operations
│   ├── auth.py        # Authentication
│   ├── bookings.py    # Booking management
│   ├── broadcast.py   # Broadcast messaging
│   ├── departures.py  # Departure management
│   ├── external.py    # External API (API key auth)
│   ├── helpers.py     # Shared helper functions
│   ├── landlord.py    # Landlord operations
│   ├── managers.py    # Agency manager CRUD
│   ├── public.py      # Public endpoints
│   ├── referrals.py   # QR code referrals
│   ├── tours.py       # Tour management
│   └── utils.py       # Endpoint utilities
└── schemas/           # Request/Response DTOs
    ├── admin_schemas.py
    ├── auth_schemas.py
    ├── booking_schemas.py
    ├── broadcast_schemas.py
    ├── departure_schemas.py
    ├── external_schemas.py
    ├── landlord_schemas.py
    ├── manager_schemas.py
    ├── public_schemas.py
    ├── referral_schemas.py
    └── tour_schemas.py
```

## Architecture Principles

### 1. Separation of Concerns
- **Endpoints**: Handle HTTP requests/responses only
- **Services**: Contain all business logic
- **Repositories**: Handle data access
- **Schemas**: Define request/response models

### 2. Dependency Flow
```
Endpoints → Services → Repositories → Database
     ↓          ↓           ↓
  Schemas    Domain     Infrastructure
```

### 3. Error Handling
- Services throw domain exceptions
- Middleware converts to HTTP responses
- Consistent error format across API

## API Routes

### Public Endpoints
- `GET /tours/search` - Search tours with filters
- `GET /tours/{id}` - Get tour details
- `GET /tours/{id}/categories` - List ticket categories
- `GET /tours/{id}/departures` - List departures
- `POST /quote` - Calculate booking price
- `GET /cities` - List cities
- `GET /tour_categories` - List tour categories

### Agency Endpoints (`/agency/*`)
- Tours CRUD
- Departures CRUD
- Bookings management
- Managers CRUD

### Admin Endpoints (`/admin/*`)
- Platform metrics
- User management
- API key management
- Commission settings

### Landlord Endpoints (`/landlord/*`)
- Apartment management
- Commission settings
- Earnings tracking
- QR code generation

### External API (`/external/*`)
- Capacity updates
- Booking exports

### Broadcast (`/departures/*`)
- Send messages to tourists
- List broadcastable departures

### Referrals (`/referrals/*`)
- Record QR code scans
- Track landlord referrals

## Authentication

The API uses JWT tokens for authentication with role-based access:
- `admin` - Platform administrators
- `agency` - Tour agencies
- `landlord` - Property landlords
- `manager` - Agency managers
- `bot_user` - Telegram bot users

External API endpoints use API keys for authentication.

## Usage Example

```python
# Using the new structure
from app.api.v1.endpoints.tours import router as tours_router
from app.services.tour_service import TourService

# Service layer handles business logic
service = TourService(session)
tour = await service.create_tour(...)

# Endpoints are thin controllers
@router.post("/", response_model=TourOut)
async def create_tour(payload: TourIn, sess: SessionDep):
    service = TourService(sess)
    tour = await service.create_tour(...)
    return TourOut.model_validate(tour)
```

## Migration from Old Structure

1. All endpoints now live under `/api/v1/`
2. Update imports from `app.api.tours` to `app.api.v1.endpoints.tours`
3. Business logic moved from endpoints to services
4. Direct database access replaced with repositories

## Testing

Each layer can be tested independently:
- Unit test services with mocked repositories
- Unit test endpoints with mocked services
- Integration tests for full flow 