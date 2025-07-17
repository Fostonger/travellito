import { format, parseISO } from 'date-fns';
import { ru, enUS } from 'date-fns/locale';

/**
 * Get current locale for date formatting
 */
export const getCurrentLocale = () => {
  // Get language from browser or use default
  const language = navigator.language || 'en-US';
  return language.startsWith('ru') ? ru : enUS;
};

/**
 * Convert UTC ISO string to local date object
 */
export const utcToLocalDate = (isoString: string): Date => {
  if (!isoString) return new Date();
  
  try {
    // Parse ISO string to date object
    const date = parseISO(isoString);
    return date;
    // Note: parseISO automatically handles the timezone conversion when displaying
    // We don't need to manually adjust with getTimezoneOffset()
  } catch (e) {
    console.error('Error parsing date:', e);
    return new Date();
  }
};

/**
 * Format date to readable string (day, month, year)
 */
export const formatDate = (dateString: string): string => {
  try {
    const date = utcToLocalDate(dateString);
    return format(date, 'PP', { locale: getCurrentLocale() });
  } catch (e) {
    console.error('Error formatting date:', e);
    return dateString;
  }
};

/**
 * Format time to 24-hour format (HH:MM)
 */
export const formatTime = (dateString: string): string => {
  try {
    const date = utcToLocalDate(dateString);
    return format(date, 'HH:mm', { locale: getCurrentLocale() });
  } catch (e) {
    console.error('Error formatting time:', e);
    return '';
  }
};

/**
 * Format date to full format with day of week (e.g. "Monday, January 1, 2023")
 */
export const formatFullDate = (dateString: string): string => {
  try {
    const date = utcToLocalDate(dateString);
    return format(date, 'PPPP', { locale: getCurrentLocale() });
  } catch (e) {
    console.error('Error formatting full date:', e);
    return dateString;
  }
};

/**
 * Get date string for grouping (removes time part)
 */
export const getDateString = (dateString: string): string => {
  try {
    const date = utcToLocalDate(dateString);
    return date.toDateString();
  } catch (e) {
    console.error('Error getting date string:', e);
    return new Date().toDateString();
  }
};

/**
 * Get departure date that handles virtual timestamp
 * @param departure The departure object with starts_at and optional virtual_timestamp
 */
export const getDepartureDate = (departure: { starts_at: string; virtual_timestamp?: number }): Date => {
  // If this was a virtual departure that got materialized, use the original timestamp
  if (departure.virtual_timestamp) {
    return new Date(departure.virtual_timestamp);
  }
  // Otherwise use the starts_at field
  return utcToLocalDate(departure.starts_at);
}; 