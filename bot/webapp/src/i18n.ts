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
    no_departures: "Нет доступных дат",
    contact_info: "Контактная информация",
    name: "Имя",
    phone: "Телефон",
    enter_name: "Введите ваше имя",
    enter_phone: "Введите номер телефона",
    select_tickets: "Выберите билеты",
    name_required: "Пожалуйста, укажите имя",
    phone_required: "Пожалуйста, укажите номер телефона",
    booking_error: "Ошибка при бронировании. Пожалуйста, попробуйте еще раз.",
    quote_error: "Ошибка при расчете стоимости. Пожалуйста, попробуйте еще раз.",
    processing: "Обработка...",
    hours: "ч",
    minutes: "мин",
    auth_required: "Требуется авторизация. Пожалуйста, перезапустите бот.",
    validation_error: "Ошибка валидации данных. Проверьте правильность заполнения формы.",
    no_tours: "Нет доступных экскурсий",
    virtual_departure_error: "Не удалось создать отправление. Пожалуйста, выберите другую дату.",
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
    no_departures: "No available dates",
    contact_info: "Contact Information",
    name: "Name",
    phone: "Phone",
    enter_name: "Enter your name",
    enter_phone: "Enter your phone number",
    select_tickets: "Select tickets",
    name_required: "Please enter your name",
    phone_required: "Please enter your phone number",
    booking_error: "Error processing booking. Please try again.",
    quote_error: "Error calculating price. Please try again.",
    processing: "Processing...",
    hours: "h",
    minutes: "min",
    auth_required: "Authentication required. Please restart the bot.",
    validation_error: "Data validation error. Please check your form inputs.",
    no_tours: "No available tours",
    virtual_departure_error: "Failed to create departure. Please select a different date.",
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