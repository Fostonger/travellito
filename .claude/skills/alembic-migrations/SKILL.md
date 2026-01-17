---
name: alembic-migrations
description: Правила работы с миграциями Alembic. Используй при изменении моделей SQLAlchemy, добавлении полей, таблиц, индексов.
---

# Alembic Migrations (web/alembic/)

## Когда нужна миграция

Миграция ОБЯЗАТЕЛЬНА при:
- Добавлении/удалении таблицы
- Добавлении/удалении/переименовании колонки
- Изменении типа данных колонки
- Добавлении/удалении индекса или constraint
- Изменении nullable/default значений

Миграция НЕ нужна при:
- Изменении relationship (без изменения FK)
- Изменении методов модели
- Добавлении computed properties

---

## Workflow создания миграции

### 1. Измени модель в `web/app/models.py`

```python
# Пример: добавление поля
class Tour(Base):
    __tablename__ = "tours"
    # ... существующие поля
    is_featured = mapped_column(Boolean, default=False, nullable=False)  # NEW
```

### 2. Сгенерируй миграцию

```bash
cd web && ../.venv/bin/alembic revision --autogenerate -m "add tour is_featured field"
```

### 3. Проверь сгенерированный файл

Открой файл в `web/alembic/versions/` и проверь:
- Корректность операций upgrade/downgrade
- Наличие `nullable`, `server_default` для новых колонок
- Правильность типов данных

### 4. Примени миграцию

```bash
cd web && ../.venv/bin/alembic upgrade head
```

---

## Правила написания миграций

### Именование
```
{revision_id}_краткое_описание_на_английском.py
```
Примеры:
- `add_user_phone_field`
- `create_landlord_commissions_table`
- `add_index_on_tour_city_id`

### Nullable и defaults

**Для новых колонок в существующих таблицах:**

```python
# Вариант 1: nullable=True (если данные могут отсутствовать)
op.add_column('tours', sa.Column('notes', sa.String(500), nullable=True))

# Вариант 2: default + nullable=False (для обязательных полей)
op.add_column('tours', sa.Column('is_active', sa.Boolean(),
    nullable=False, server_default=sa.text('true')))
```

**Никогда:**
```python
# ПЛОХО — упадёт на существующих данных
op.add_column('tours', sa.Column('required_field', sa.String(100), nullable=False))
```

### Индексы

```python
# Создание индекса
op.create_index('ix_tours_city_id', 'tours', ['city_id'])

# Составной индекс
op.create_index('ix_departures_tour_date', 'departures', ['tour_id', 'starts_at'])

# Уникальный индекс
op.create_index('ix_users_email', 'users', ['email'], unique=True)
```

### Foreign Keys

```python
op.add_column('users', sa.Column('apartment_id', sa.Integer(), nullable=True))
op.create_foreign_key(
    'fk_users_apartment_id',
    'users', 'apartments',
    ['apartment_id'], ['id'],
    ondelete='SET NULL'
)
```

---

## Data Migrations

Для миграций с преобразованием данных:

```python
from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import table, column

def upgrade():
    # Добавляем колонку
    op.add_column('tours', sa.Column('status', sa.String(20), nullable=True))

    # Заполняем существующие записи
    tours = table('tours', column('id'), column('status'))
    op.execute(tours.update().values(status='active'))

    # Делаем NOT NULL после заполнения
    op.alter_column('tours', 'status', nullable=False)

def downgrade():
    op.drop_column('tours', 'status')
```

---

## Типичные ошибки

### 1. Забыт downgrade
```python
def downgrade():
    pass  # ПЛОХО — невозможно откатить

def downgrade():
    op.drop_column('tours', 'is_featured')  # ХОРОШО
```

### 2. Неправильный порядок операций
```python
# ПЛОХО — FK ссылается на несуществующую таблицу
op.add_column('users', sa.Column('role_id', sa.ForeignKey('roles.id')))
op.create_table('roles', ...)

# ХОРОШО — сначала таблица, потом FK
op.create_table('roles', ...)
op.add_column('users', sa.Column('role_id', sa.ForeignKey('roles.id')))
```

### 3. Изменение типа без конвертации
```python
# ПЛОХО — потеря данных
op.alter_column('tours', 'price', type_=sa.Integer())  # было Numeric

# ХОРОШО — явная конвертация
op.execute("UPDATE tours SET price = ROUND(price)")
op.alter_column('tours', 'price', type_=sa.Integer())
```

---

## Полезные команды

```bash
# Текущая ревизия
cd web && ../.venv/bin/alembic current

# История миграций
cd web && ../.venv/bin/alembic history

# Откат на одну миграцию
cd web && ../.venv/bin/alembic downgrade -1

# Откат до конкретной ревизии
cd web && ../.venv/bin/alembic downgrade <revision_id>

# Показать SQL без выполнения
cd web && ../.venv/bin/alembic upgrade head --sql
```

---

## Чеклист перед коммитом миграции

- [ ] Модель в `models.py` соответствует миграции
- [ ] `upgrade()` и `downgrade()` симметричны
- [ ] Новые NOT NULL колонки имеют `server_default` или заполнены данными
- [ ] Индексы добавлены для FK и часто используемых фильтров
- [ ] Миграция применяется без ошибок: `alembic upgrade head`
- [ ] Откат работает: `alembic downgrade -1` + `alembic upgrade head`
