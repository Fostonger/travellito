/* Lightweight i18n helper – keep it dependency-free for the mini-app. */
export type Lang = "ru" | "en";

// -----------------------------------------------------------------------------
//  Language detection
// -----------------------------------------------------------------------------

function detectLang(): Lang {
  // 1) URL query param ?lang=ru|en (preferred)
  const qs = new URLSearchParams(window.location.search);
  const qp = qs.get("lang");
  if (qp === "ru" || qp === "en") return qp;
  // 2) Browser / Telegram@WebApp language, e.g. "ru-RU"
  if (navigator.language && navigator.language.toLowerCase().startsWith("ru")) return "ru";
  return "en";
}

export const lang: Lang = detectLang();

// -----------------------------------------------------------------------------
//  Messages
// -----------------------------------------------------------------------------

const messages: Record<Lang, Record<string, string>> = {
  ru: {
    loading: "Загрузка…",
    available_tours: "Доступные экскурсии",
    seats_left: "осталось мест",
    my_bookings: "Мои бронирования",
    back: "Назад",
    cancel: "Отменить",
    checkout: "Бронирование – {date}",
    total: "Итого:",
    confirm: "Подтвердить бронирование",
    booking_confirmed: "Бронирование подтверждено!",
    missing_ctx: "Недостаточно данных",
    not_found: "Не найдено",
    upcoming_departures: "Ближайшие даты",
    book: "Забронировать",
    seats: "мест",
  },
  en: {
    loading: "Loading…",
    available_tours: "Available Tours",
    seats_left: "seats left",
    my_bookings: "My Bookings",
    back: "Back",
    cancel: "Cancel",
    checkout: "Checkout – {date}",
    total: "Total:",
    confirm: "Confirm Booking",
    booking_confirmed: "Booking confirmed!",
    missing_ctx: "Missing context",
    not_found: "Not found",
    upcoming_departures: "Upcoming departures",
    book: "Book",
    seats: "seats",
  },
};

export function t(key: string, vars: Record<string, string | number> = {}): string {
  let str = messages[lang][key] || key;
  for (const [k, v] of Object.entries(vars)) str = str.replace(`{${k}}`, String(v));
  return str;
}

export function fmtPrice(value: string | number): string {
  const num = typeof value === "string" ? value : value.toString();
  return `${num} ₽`;
} 