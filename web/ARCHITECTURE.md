# Travellito Backend Architecture

## Clean Architecture Implementation

This backend follows Clean Architecture principles with clear separation of concerns across multiple layers.

### Architecture Layers

```
┌─────────────────────────────────────────────────────────────┐
│                    Presentation Layer                        │
│                  (FastAPI Controllers)                       │
├─────────────────────────────────────────────────────────────┤
│                    Application Layer                         │
│                   (Business Services)                        │
├─────────────────────────────────────────────────────────────┤
│                      Domain Layer                            │
│                  (Entities & Business Rules)                 │
├─────────────────────────────────────────────────────────────┤
│                  Infrastructure Layer                        │
│              (Repositories, External Services)               │
└─────────────────────────────────────────────────────────────┘
```

```mermaid
graph TB
    subgraph "Client Layer"
        A[Web Browser]
        B[Mobile App]
        C[API Consumer]
    end
    
    subgraph "API Layer /api/v1"
        D[Auth Endpoints<br/>Login/Logout/Refresh]
        E[Tour Endpoints<br/>CRUD Operations]
        F[Departure Endpoints<br/>Schedule Management]
        G[Booking Endpoints<br/>Reservation Management]
        H[Admin Endpoints<br/>Platform Management]
    end
    
    subgraph "Service Layer"
        I[AuthService<br/>Authentication Logic]
        J[TourService<br/>Tour Business Rules]
        K[DepartureService<br/>Schedule Logic]
        L[BookingService<br/>Reservation Logic]
        M[AdminService<br/>Admin Operations]
    end
    
    subgraph "Repository Layer"
        N[UserRepository]
        O[TourRepository]
        P[DepartureRepository]
        Q[PurchaseRepository]
        R[AgencyRepository]
    end
    
    subgraph "Database"
        S[(PostgreSQL)]
    end
    
    subgraph "External Services"
        T[S3/MinIO<br/>File Storage]
        U[Telegram Bot API]
        V[External Agency APIs]
    end
    
    A --> D
    B --> D
    C --> D
    
    D --> I
    E --> J
    F --> K
    G --> L
    H --> M
    
    I --> N
    J --> O
    J --> T
    K --> P
    K --> O
    L --> Q
    L --> P
    M --> N
    M --> O
    M --> R
    
    N --> S
    O --> S
    P --> S
    Q --> S
    R --> S
    
    style A fill:#e3f2fd
    style B fill:#e3f2fd
    style C fill:#e3f2fd
    style I fill:#fff3e0
    style J fill:#fff3e0
    style K fill:#fff3e0
    style L fill:#fff3e0
    style M fill:#fff3e0
    style N fill:#e8f5e9
    style O fill:#e8f5e9
    style P fill:#e8f5e9
    style Q fill:#e8f5e9
    style R fill:#e8f5e9
```

### Dependency Flow

- Controllers → Services → Repositories → Database
- Services → Domain Models
- All layers → Core (shared utilities)

### Key Principles

1. **Dependency Inversion**: High-level modules don't depend on low-level modules
2. **Single Responsibility**: Each class has one reason to change
3. **Interface Segregation**: Clients depend only on interfaces they use
4. **Open/Closed**: Open for extension, closed for modification

### Benefits

- **Testability**: Each layer can be tested independently
- **Maintainability**: Clear boundaries and responsibilities
- **Scalability**: Easy to add new features without affecting existing code
- **Flexibility**: Can swap implementations (e.g., different databases)

### Example Flow: Creating a Tour

1. **Controller** receives HTTP request
2. **Controller** validates request data using Pydantic schema
3. **Controller** calls **Service** with validated data
4. **Service** applies business rules and validation
5. **Service** calls **Repository** to persist data
6. **Repository** handles database operations
7. **Service** returns domain model
8. **Controller** serializes response using Pydantic schema

This architecture ensures that business logic is independent of frameworks, UI, database, and external agencies. 