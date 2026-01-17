---
name: react-typescript-style
description: Правила написания React/TypeScript кода для WebApp (bot/webapp/). Используй при создании компонентов, страниц, хуков, работе с API и состоянием.
---

# React/TypeScript Coding Style (bot/webapp/)

## Структура проекта

```
bot/webapp/src/
├── api/           # API клиент и хуки для запросов
├── components/    # Переиспользуемые компоненты
│   └── ui/        # Базовые UI компоненты (Button, Card, Badge...)
├── pages/         # Страницы приложения (App, TourDetail, Checkout, MyBookings)
├── utils/         # Утилиты (store, dateUtils, analytics)
├── auth.ts        # Аутентификация через Telegram WebApp
├── i18n.ts        # Интернационализация
└── types.ts       # Общие типы
```

---

## Общие принципы

### TypeScript
- Типизация обязательна для props, возвращаемых значений функций, состояния
- Избегай `any` — используй `unknown` + type guards или конкретные типы
- `@ts-nocheck` допустим ТОЛЬКО для legacy-файлов, не добавляй в новый код
- Интерфейсы для props компонентов, типы для union/утилит

```typescript
// Props компонента
interface TourCardProps {
  tour: Tour;
  onClick?: () => void;
}

// Union типы
type BookingStatus = 'pending' | 'confirmed' | 'cancelled';
```

### Компоненты
- Функциональные компоненты (никаких классов)
- Именование: PascalCase для компонентов, camelCase для хуков
- Один компонент = один файл (исключение: мелкие вспомогательные компоненты внутри файла)

```typescript
// Хорошо
export function TourCard({ tour, onClick }: TourCardProps) {
  return <div onClick={onClick}>{tour.title}</div>;
}

// Плохо — default export без имени
export default function({ tour }) { ... }
```

---

## Работа с данными

### TanStack Query (react-query)
Используется для всех API-запросов. Паттерн из проекта:

```typescript
// api/client.ts — определение хука
export function useTour(id: string | undefined) {
  return useQuery({
    queryKey: ['tour', id],
    queryFn: () => fetchTourById(id!),
    enabled: !!id,
    staleTime: 10 * 60 * 1000, // 10 минут
  });
}

// Использование в компоненте
const { data: tour, isLoading, error } = useTour(id);
```

**Правила:**
- `queryKey` должен быть уникальным и содержать все зависимости
- `enabled` для условных запросов (когда id может быть undefined)
- `staleTime` для кеширования (5-10 минут для справочных данных)

### Axios
- Используй `apiClient` из `api/client.ts` (уже настроен с interceptors)
- Не создавай новые экземпляры axios
- Обработка ошибок через interceptors (auth.ts)

---

## Состояние

### Локальное состояние
- `useState` для простого UI состояния
- `useReducer` для сложной логики с множеством переходов

### Глобальное состояние
- Файл `utils/store.ts` для фильтров и общего состояния
- Не храни в глобальном состоянии то, что можно получить через query

---

## Telegram WebApp интеграция

### Инициализация
```typescript
// Проверка окружения
const isInTelegram = !!window.Telegram?.WebApp;

// Получение initData для аутентификации
const initData = window.Telegram.WebApp.initData;

// Сигнал готовности
window.Telegram.WebApp.ready();
```

### Аутентификация
Используй функции из `auth.ts`:
- `authenticateWithTelegram()` — аутентификация через initData
- `getAccessToken()` / `getRefreshToken()` — токены из localStorage
- `setupAxiosAuth()` — настройка interceptors

---

## Стилизация

### TailwindCSS
- Используй utility-классы напрямую
- Для сложных компонентов — `cn()` утилита для условных классов
- Анимации через `tailwindcss-animate`

```typescript
import { cn } from '../utils/cn';

<button className={cn(
  'px-4 py-2 rounded-md',
  isActive && 'bg-primary text-white',
  isDisabled && 'opacity-50 cursor-not-allowed'
)}>
```

### UI компоненты
Переиспользуй из `components/ui/`:
- `Button`, `Card`, `Badge`, `Skeleton`, `Tabs`
- Не дублируй стили — расширяй существующие компоненты

---

## Обработка ошибок

```typescript
// В компонентах — graceful degradation
if (error) {
  return <div className="text-center text-muted-foreground">{t('error_loading')}</div>;
}

// Loading states
if (isLoading) {
  return <TourDetailsSkeleton />;
}
```

---

## Интернационализация

Используй функции из `i18n.ts`:

```typescript
import { t, fmtPrice } from '../i18n';

<span>{t('book')}</span>
<span>{fmtPrice(1500)}</span>  // "1 500 ₽"
```

---

## Чеклист для нового кода

- [ ] Типизация без `any`
- [ ] Компонент экспортирован с именем (не anonymous default)
- [ ] API-запросы через TanStack Query хуки
- [ ] Loading и error состояния обработаны
- [ ] Переиспользованы UI компоненты из `components/ui/`
- [ ] Тексты через `t()` для i18n
- [ ] `tsc --noEmit` проходит без ошибок
