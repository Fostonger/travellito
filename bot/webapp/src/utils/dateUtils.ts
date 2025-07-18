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
 * The server sends dates in UTC but without the timezone indicator
 */
export const utcToLocalDate = (isoString: string): Date => {
  if (!isoString) return new Date();
  
  try {
    // The server sends UTC times but without the 'Z' indicator
    // First, create a UTC date by appending 'Z' if it's not present
    const hasTimezoneInfo = isoString.endsWith('Z') || 
                           isoString.includes('+');
    
    console.log('hasTimezoneInfo', hasTimezoneInfo);
    console.log('isoString', isoString);
    
    if (!hasTimezoneInfo) {
      // Append 'Z' to indicate this is UTC time
      const utcString = `${isoString}Z`;
      
      // Debug information
      console.debug('[dateUtils] Converting UTC to local:', { 
        original: isoString,
        withZ: utcString,
        result: parseISO(utcString).toString(),
        offset: new Date().getTimezoneOffset()
      });
      
      // Now parseISO will correctly interpret it as UTC
      return parseISO(utcString);
    }
    
    // If it already has timezone info, just parse it normally
    return parseISO(isoString);
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
    // The timestamp is in milliseconds since epoch and represents the UTC time
    const date = new Date(departure.virtual_timestamp);
    console.log('Using virtual timestamp:', departure.virtual_timestamp, 
                'Date:', date.toString(), 
                'UTC:', date.toUTCString());
    return date;
  }
  // Otherwise use the starts_at field
  return utcToLocalDate(departure.starts_at);
};

/**
 * Test function to debug UTC to local time conversion
 * You can call this in the browser console to verify the conversion works correctly
 */
export const testDateConversion = (isoString: string): void => {
  console.group('Date Conversion Test');
  console.log('Input:', isoString);
  
  // Test with our function (UTC → Local)
  const localDate = utcToLocalDate(isoString);
  console.log('After utcToLocalDate:', localDate.toString());
  console.log('Formatted time:', formatTime(isoString));
  console.log('Formatted date:', formatDate(isoString));
  
  // Test what happens with direct parsing (no Z appended)
  const directParse = parseISO(isoString);
  console.log('Direct parseISO (no Z):', directParse.toString());
  
  // Test with explicit Z
  const withZ = parseISO(`${isoString}Z`);
  console.log('ParseISO with Z:', withZ.toString());
  
  console.log('Your timezone offset:', new Date().getTimezoneOffset() / -60, 'hours');
  console.groupEnd();
}; 