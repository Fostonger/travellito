---
name: python-testing-practices
description: Правила написания production-level тестов на Python. Используй при создании unit и интеграционных тестов. Фокус на тестах, которые реально проверяют функциональность, а не на покрытии ради покрытия.
---

# Python Testing Practices

## Философия тестирования

**Тесты пишутся не ради покрытия, а ради уверенности в коде.**

Хороший тест:
- Ломается когда код работает неправильно
- НЕ ломается когда код работает правильно
- Документирует ожидаемое поведение
- Позволяет безопасно рефакторить

Плохой тест:
- Проверяет implementation details вместо поведения
- Дублирует код (тест = копия реализации)
- Хрупкий — ломается при любом изменении
- Зелёный всегда, независимо от багов

---

## Структура тестов

```
web/tests/
├── conftest.py           # Общие фикстуры
├── unit/                 # Unit тесты
│   ├── test_booking_service.py
│   ├── test_tour_service.py
│   └── test_validators.py
├── integration/          # Интеграционные тесты
│   ├── test_booking_api.py
│   ├── test_auth_flow.py
│   └── test_telegram_webhook.py
└── fixtures/             # Тестовые данные
    └── tours.py
```

---

## Unit тесты

### Когда писать unit тесты

**Обязательно:**
- Бизнес-логика в сервисах (расчёты, валидации, state transitions)
- Чистые функции с нетривиальной логикой
- Парсеры и трансформеры данных
- Валидаторы

**Не нужно:**
- Простые CRUD операции без логики
- Прямые прокси к ORM/библиотекам
- Конфигурация и константы

### Пример: тест бизнес-логики

```python
# web/tests/unit/test_booking_service.py
import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

from app.services.booking_service import BookingService
from app.core import BusinessLogicError, NotFoundError


class TestBookingStatusTransition:
    """Тесты переходов статусов бронирования."""

    @pytest.fixture
    def mock_session(self):
        return AsyncMock()

    @pytest.fixture
    def mock_repository(self, mock_session):
        repo = AsyncMock()
        return repo

    @pytest.fixture
    def service(self, mock_session, mock_repository, monkeypatch):
        svc = BookingService(mock_session)
        monkeypatch.setattr(svc, 'repository', mock_repository)
        return svc

    async def test_confirm_pending_booking_succeeds(self, service, mock_repository):
        """Подтверждение pending бронирования должно работать."""
        # Arrange
        booking = MagicMock()
        booking.status = "pending"
        booking.departure.tour.agency_id = 1
        mock_repository.get_with_details.return_value = booking
        mock_repository.update_status.return_value = booking

        # Act
        result = await service.update_booking_status(
            booking_id=123,
            agency_id=1,
            status="confirmed"
        )

        # Assert
        mock_repository.update_status.assert_called_once_with(
            123, "confirmed", tourist_notified=False
        )

    async def test_confirm_already_confirmed_raises_error(self, service, mock_repository):
        """Повторное подтверждение должно выбрасывать ошибку."""
        # Arrange
        booking = MagicMock()
        booking.status = "confirmed"  # Уже подтверждено
        booking.departure.tour.agency_id = 1
        mock_repository.get_with_details.return_value = booking

        # Act & Assert
        with pytest.raises(BusinessLogicError) as exc_info:
            await service.update_booking_status(
                booking_id=123,
                agency_id=1,
                status="confirmed"
            )
        assert "already confirmed" in str(exc_info.value)

    async def test_wrong_agency_returns_not_found(self, service, mock_repository):
        """Бронирование чужого агентства должно возвращать NotFound."""
        # Arrange
        booking = MagicMock()
        booking.departure.tour.agency_id = 999  # Другое агентство
        mock_repository.get_with_details.return_value = booking

        # Act & Assert
        with pytest.raises(NotFoundError):
            await service.update_booking_status(
                booking_id=123,
                agency_id=1,  # Не совпадает
                status="confirmed"
            )
```

### Паттерн Arrange-Act-Assert

Каждый тест должен чётко разделяться на три секции:

```python
async def test_cancel_booking_before_cutoff(self, service):
    # Arrange — подготовка данных и моков
    booking = create_booking(
        status="pending",
        departure_at=datetime.utcnow() + timedelta(hours=48)
    )

    # Act — вызов тестируемого кода
    result = await service.cancel_booking(booking.id, booking.user_id)

    # Assert — проверка результата
    assert result is True
    assert booking.status == "cancelled"
```

---

## Интеграционные тесты

### Когда писать интеграционные тесты

**Обязательно:**
- API endpoints (happy path + основные ошибки)
- Аутентификация и авторизация
- Сложные запросы к БД (joins, aggregations)
- Внешние интеграции (с моками внешних сервисов)

**Условия для интеграционных тестов:**
1. Код взаимодействует с несколькими компонентами (DB + Service + API)
2. Важно проверить правильность SQL/ORM запросов
3. Критический user flow (checkout, auth)

### Пример: тест API endpoint

```python
# web/tests/integration/test_booking_api.py
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from app.models import User, Tour, Departure, Purchase


@pytest.fixture
async def auth_client(async_client: AsyncClient, test_user: User):
    """Клиент с авторизацией."""
    # Получаем токен
    response = await async_client.post("/api/v1/auth/login", json={
        "email": test_user.email,
        "password": "testpass"
    })
    token = response.json()["access_token"]
    async_client.headers["Authorization"] = f"Bearer {token}"
    return async_client


class TestBookingAPI:
    """Интеграционные тесты API бронирований."""

    async def test_create_booking_success(
        self,
        auth_client: AsyncClient,
        test_departure: Departure,
        db_session: AsyncSession
    ):
        """Успешное создание бронирования через API."""
        # Act
        response = await auth_client.post("/api/v1/bookings", json={
            "departure_id": test_departure.id,
            "items": [
                {"category_id": test_departure.tour.categories[0].id, "qty": 2}
            ]
        })

        # Assert
        assert response.status_code == 201
        data = response.json()
        assert data["status"] == "pending"
        assert data["qty"] == 2

        # Verify in DB
        booking = await db_session.get(Purchase, data["id"])
        assert booking is not None
        assert booking.departure_id == test_departure.id

    async def test_create_booking_no_seats_returns_400(
        self,
        auth_client: AsyncClient,
        sold_out_departure: Departure
    ):
        """Бронирование на sold out departure возвращает 400."""
        response = await auth_client.post("/api/v1/bookings", json={
            "departure_id": sold_out_departure.id,
            "items": [{"category_id": 1, "qty": 1}]
        })

        assert response.status_code == 400
        assert "seats" in response.json()["detail"].lower()

    async def test_unauthorized_returns_401(self, async_client: AsyncClient):
        """Запрос без токена возвращает 401."""
        response = await async_client.post("/api/v1/bookings", json={})
        assert response.status_code == 401
```

---

## Фикстуры

### Базовые фикстуры (conftest.py)

```python
# web/tests/conftest.py
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from httpx import AsyncClient

from app.main import app
from app.models import Base
from app.database import get_session


@pytest.fixture(scope="session")
def event_loop():
    """Один event loop на всю сессию тестов."""
    import asyncio
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def db_session():
    """Сессия БД с откатом после теста."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def async_client(db_session: AsyncSession):
    """HTTP клиент для тестов API."""
    app.dependency_overrides[get_session] = lambda: db_session
    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()
```

### Фикстуры для данных

```python
# web/tests/fixtures/tours.py
import pytest_asyncio
from datetime import datetime, timedelta

from app.models import Agency, Tour, Departure, TicketCategory


@pytest_asyncio.fixture
async def test_agency(db_session):
    agency = Agency(name="Test Agency")
    db_session.add(agency)
    await db_session.commit()
    return agency


@pytest_asyncio.fixture
async def test_tour(db_session, test_agency):
    tour = Tour(
        agency_id=test_agency.id,
        title="Test Tour",
        description="Test description",
        city_id=1
    )
    db_session.add(tour)
    await db_session.commit()

    category = TicketCategory(tour_id=tour.id, name="Adult", price=1000)
    db_session.add(category)
    await db_session.commit()

    tour.categories = [category]
    return tour


@pytest_asyncio.fixture
async def test_departure(db_session, test_tour):
    departure = Departure(
        tour_id=test_tour.id,
        starts_at=datetime.utcnow() + timedelta(days=7),
        capacity=20
    )
    db_session.add(departure)
    await db_session.commit()
    return departure
```

---

## Что НЕ тестировать

### 1. Тривиальный код
```python
# НЕ НУЖЕН тест для:
class User(Base):
    @property
    def full_name(self):
        return f"{self.first} {self.last}"
```

### 2. Framework/library код
```python
# НЕ НУЖЕН тест для:
async def get_user(session, user_id: int):
    return await session.get(User, user_id)  # Это тест SQLAlchemy, не нашего кода
```

### 3. Моки ради моков
```python
# ПЛОХО — тест ничего не проверяет
def test_service_calls_repository(mock_repo):
    service.do_something()
    mock_repo.save.assert_called_once()  # И что? Это не гарантирует корректность
```

---

## Анти-паттерны

### 1. Тест-зеркало
```python
# ПЛОХО — тест повторяет реализацию
def test_calculate_total():
    items = [{"price": 100, "qty": 2}, {"price": 50, "qty": 1}]
    # Тест делает то же самое что и код
    expected = sum(i["price"] * i["qty"] for i in items)
    assert calculate_total(items) == expected

# ХОРОШО — тест проверяет конкретный случай
def test_calculate_total():
    items = [{"price": 100, "qty": 2}, {"price": 50, "qty": 1}]
    assert calculate_total(items) == 250  # Конкретное ожидаемое значение
```

### 2. Слишком много моков
```python
# ПЛОХО — замокано всё, тест ничего не проверяет
def test_complex_flow(mock_a, mock_b, mock_c, mock_d, mock_e):
    mock_a.return_value = mock_b
    mock_b.return_value = mock_c
    # ... и т.д.

# ХОРОШО — интеграционный тест или unit тест с минимумом моков
```

### 3. Проверка implementation details
```python
# ПЛОХО — завязка на внутреннюю реализацию
def test_caching():
    service.get_data()
    assert service._cache["key"] == "value"  # Приватный атрибут

# ХОРОШО — проверка поведения
def test_caching_returns_same_result():
    result1 = service.get_data()
    result2 = service.get_data()
    assert result1 == result2
```

---

## Команды запуска

```bash
# Все тесты
cd web && ../.venv/bin/pytest -v

# Только unit тесты
cd web && ../.venv/bin/pytest tests/unit -v

# Только интеграционные
cd web && ../.venv/bin/pytest tests/integration -v

# Конкретный файл/тест
cd web && ../.venv/bin/pytest tests/unit/test_booking_service.py::TestBookingStatusTransition -v

# С покрытием (но не ради покрытия!)
cd web && ../.venv/bin/pytest --cov=app --cov-report=term-missing
```

---

## Чеклист для теста

- [ ] Тест проверяет поведение, а не реализацию
- [ ] Понятно что тест проверяет из названия
- [ ] Arrange-Act-Assert структура
- [ ] Минимум моков (только внешние зависимости)
- [ ] Тест падает если сломать тестируемый код
- [ ] Нет магических чисел — понятно откуда значения
