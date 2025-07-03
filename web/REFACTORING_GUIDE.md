# Backend Refactoring Guide

## Overview

This document describes the refactoring of the Travellito backend from a monolithic structure to a clean, layered architecture following SOLID principles.

## Problems with Original Architecture

1. **Single Responsibility Principle Violations**
   - `main.py` (551 lines) mixed routes, business logic, and infrastructure
   - API files like `agency.py` (873 lines) contained everything from validation to database queries

2. **No Separation of Concerns**
   - Business logic mixed with HTTP handling
   - Direct database access from route handlers
   - No abstraction layers

3. **High Coupling**
   - Routes directly dependent on database models
   - No dependency injection
   - Hard to test in isolation

## New Architecture

### Layer Structure

```
app/
├── core/                    # Core utilities and base classes
│   ├── base.py             # Base repository and service classes
│   ├── config.py           # Configuration management
│   └── exceptions.py       # Custom exception hierarchy
│
├── domain/                  # Domain models and business entities
│   └── (models remain in models.py for now)
│
├── infrastructure/          # External dependencies
│   ├── database.py         # Database configuration
│   └── repositories/       # Data access layer
│       ├── tour_repository.py
│       ├── departure_repository.py
│       └── agency_repository.py
│
├── services/               # Business logic layer
│   ├── tour_service.py    # Tour business logic
│   └── departure_service.py
│
└── api/
    └── v1/
        ├── endpoints/      # HTTP endpoints (thin controllers)
        │   └── tours.py
        ├── schemas/        # Request/Response DTOs
        │   └── tour_schemas.py
        └── middleware.py   # Exception handling
```

### Key Design Patterns

1. **Repository Pattern**
   - Abstracts data access
   - Provides testable interface
   - Enables switching data sources

2. **Service Layer**
   - Contains all business logic
   - Orchestrates operations
   - Handles validation and business rules

3. **Dependency Injection**
   - Services receive repositories
   - Loose coupling between layers
   - Easy to mock for testing

4. **Custom Exceptions**
   - Consistent error handling
   - Business-specific exceptions
   - Automatic HTTP status mapping

## SOLID Principles Applied

### Single Responsibility Principle (SRP)
- Each class has one reason to change
- Repositories handle data access only
- Services handle business logic only
- Controllers handle HTTP concerns only

### Open/Closed Principle (OCP)
- Base classes can be extended without modification
- New repositories inherit from BaseRepository
- New services inherit from BaseService

### Liskov Substitution Principle (LSP)
- Repository interfaces can be swapped
- Any repository implementing IRepository works

### Interface Segregation Principle (ISP)
- Small, focused interfaces
- Repositories have specific methods for their domain

### Dependency Inversion Principle (DIP)
- High-level modules don't depend on low-level modules
- Services depend on repository interfaces, not implementations
- Controllers depend on services, not direct database access

## Migration Guide

### Phase 1: Core Infrastructure ✅
- Created base classes and exceptions
- Set up configuration management
- Created database infrastructure

### Phase 2: Repositories ✅
- Created repository pattern implementations
- Abstracted data access

### Phase 3: Services ✅
- Moved business logic to services
- Separated validation and orchestration

### Phase 4: API Refactoring (In Progress)
- Create thin controllers
- Use dependency injection
- Implement consistent error handling

### Phase 5: Complete Migration (TODO)
- Refactor all remaining endpoints
- Remove old code
- Update tests

## Benefits

1. **Maintainability**
   - Clear separation of concerns
   - Easy to locate and modify code
   - Consistent patterns throughout

2. **Testability**
   - Each layer can be tested in isolation
   - Easy to mock dependencies
   - Unit tests for business logic

3. **Scalability**
   - Easy to add new features
   - Can swap implementations
   - Supports microservices migration

4. **Developer Experience**
   - Clear code organization
   - Self-documenting structure
   - Reduced cognitive load

## Example: Tour Creation Flow

### Old Way (main.py)
```python
@app.post("/admin/tours")
async def create_tour(data, images, user):
    # Everything mixed together:
    # - Authentication
    # - Validation
    # - Database access
    # - Business logic
    # - Image upload
    # - Response formatting
```

### New Way (Clean Architecture)
```python
# Controller (thin, HTTP concerns only)
@router.post("/", response_model=TourOut)
async def create_tour(payload: TourIn, sess: SessionDep, user=Depends(current_user)):
    service = TourService(sess)
    tour = await service.create_tour(...)  # Delegate to service
    return TourOut.model_validate(tour)

# Service (business logic)
class TourService:
    async def create_tour(self, ...):
        # Validation
        # Business rules
        # Orchestration
        return await self.tour_repository.create(...)

# Repository (data access)
class TourRepository:
    async def create(self, obj_in: dict):
        # Pure database operations
        # No business logic
```

## Next Steps

1. Complete refactoring of remaining endpoints
2. Add comprehensive unit tests
3. Add integration tests
4. Update API documentation
5. Performance optimization
6. Consider event-driven patterns for complex workflows 