import axios from 'axios';
import { useQuery } from '@tanstack/react-query';
import { FilterState } from '../utils/store';
import { Tour } from '../types';

// API base URL
// @ts-ignore - import.meta.env is defined by Vite
const apiBase = import.meta.env.VITE_API_BASE || 'https://api.trycloudflare.com/api/v1';

// Create axios instance with default config
const apiClient = axios.create({
  baseURL: apiBase,
  withCredentials: true,
});

/**
 * Build query parameters for tour search
 */
const buildTourSearchParams = (filters: Partial<FilterState> = {}) => {
  const params: Record<string, any> = {
    limit: 50,
    ...filters,
  };

  // Format time filters with timezone offset
  if (params.timeFrom || params.timeTo) {
    // Get timezone offset in format +HH:MM or -HH:MM
    const date = new Date();
    const offsetMinutes = date.getTimezoneOffset();
    const offsetHours = Math.floor(Math.abs(offsetMinutes) / 60);
    const offsetMins = Math.abs(offsetMinutes) % 60;
    
    // Format as +HH:MM or -HH:MM (note: getTimezoneOffset returns inverse sign)
    const offsetSign = offsetMinutes > 0 ? '-' : '+';
    const offsetFormatted = `${offsetSign}${String(offsetHours).padStart(2, '0')}:${String(offsetMins).padStart(2, '0')}`;
    
    // Add timezone info to time filters
    if (params.timeFrom) {
      params.time_from = `${params.timeFrom}${offsetFormatted}`;
      delete params.timeFrom;
    }
    
    if (params.timeTo) {
      params.time_to = `${params.timeTo}${offsetFormatted}`;
      delete params.timeTo;
    }
  }

  // Rename filter keys to match API expectations
  if (params.priceMin !== undefined) {
    params.price_min = params.priceMin;
    delete params.priceMin;
  }
  if (params.priceMax !== undefined) {
    params.price_max = params.priceMax;
    delete params.priceMax;
  }
  if (params.dateFrom !== undefined) {
    params.date_from = params.dateFrom;
    delete params.dateFrom;
  }
  if (params.dateTo !== undefined) {
    params.date_to = params.dateTo;
    delete params.dateTo;
  }

  return params;
};

/**
 * Fetch tours with filters
 */
export async function fetchTours(filters: Partial<FilterState> = {}) {
  const params = buildTourSearchParams(filters);
  
  // Use URLSearchParams to properly handle array parameters
  const queryParams = new URLSearchParams();
  
  Object.entries(params).forEach(([key, value]) => {
    if (Array.isArray(value)) {
      // For arrays like categories, add multiple parameters with the same name
      value.forEach(item => {
        queryParams.append(key, item);
      });
    } else if (value !== undefined && value !== null && value !== '') {
      queryParams.append(key, String(value));
    }
  });
  
  // Build the URL with query parameters
  let url = '/public/tours/search';
  const queryString = queryParams.toString();
  if (queryString) {
    url += `?${queryString}`;
  }
  
  const response = await apiClient.get(url);
  return response.data;
}

/**
 * Fetch tour details by ID
 */
export async function fetchTourById(id: string) {
  const response = await apiClient.get(`/public/tours/${id}`);
  return response.data;
}

/**
 * Fetch tour departures by tour ID
 */
export async function fetchTourDepartures(tourId: string) {
  const response = await apiClient.get(`/public/tours/${tourId}/departures`, {
    params: { limit: 30 }
  });
  return response.data;
}

// React Query hooks for data fetching with cache
export function useTours(filters: Partial<FilterState> = {}) {
  // Create a stable query key including all non-empty filters
  const queryKey = ['tours'];
  Object.entries(filters).forEach(([key, value]) => {
    if (Array.isArray(value) ? value.length > 0 : value) {
      queryKey.push(key, JSON.stringify(value));
    }
  });

  return useQuery({
    queryKey,
    queryFn: () => fetchTours(filters),
    staleTime: 5 * 60 * 1000, // 5 minutes
  });
}

export function useTour(id: string | undefined) {
  return useQuery({
    queryKey: ['tour', id],
    queryFn: () => fetchTourById(id!),
    enabled: !!id,
    staleTime: 10 * 60 * 1000, // 10 minutes
  });
}

export function useTourDepartures(tourId: string | undefined) {
  return useQuery({
    queryKey: ['tourDepartures', tourId],
    queryFn: () => fetchTourDepartures(tourId!),
    enabled: !!tourId,
    staleTime: 5 * 60 * 1000, // 5 minutes
  });
}

export default apiClient; 