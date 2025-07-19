// Store for persisting app state
import React, { useEffect } from 'react';

// Type for filter state
export interface FilterState {
  categories: string[];
  priceMin: string;
  priceMax: string;
  dateFrom: string;
  dateTo: string;
  timeFrom: string;
  timeTo: string;
}

// Default initial filter state
export const initialFilterState: FilterState = {
  categories: [],
  priceMin: '',
  priceMax: '',
  dateFrom: '',
  dateTo: '',
  timeFrom: '',
  timeTo: ''
};

// Store keys
const FILTERS_STORAGE_KEY = 'travellito_filters';

/**
 * Load filters from localStorage
 */
export function loadFilters(): FilterState {
  try {
    const savedFilters = localStorage.getItem(FILTERS_STORAGE_KEY);
    if (savedFilters) {
      return JSON.parse(savedFilters) as FilterState;
    }
  } catch (error) {
    console.error('Error loading filters from localStorage:', error);
  }
  return initialFilterState;
}

/**
 * Save filters to localStorage
 */
export function saveFilters(filters: FilterState): void {
  try {
    localStorage.setItem(FILTERS_STORAGE_KEY, JSON.stringify(filters));
  } catch (error) {
    console.error('Error saving filters to localStorage:', error);
  }
}

/**
 * Hook to manage filters with automatic persistence
 */
export function usePersistedFilters(
  initialState: FilterState = loadFilters(),
  onChange?: (filters: FilterState) => void
): [FilterState, (newFilters: FilterState) => void] {
  // Initialize state from localStorage or default
  const [filters, setFiltersState] = React.useState<FilterState>(initialState);
  
  // Update localStorage when filters change
  useEffect(() => {
    saveFilters(filters);
    if (onChange) {
      onChange(filters);
    }
  }, [filters, onChange]);
  
  // Set filters with localStorage persistence
  const setFilters = (newFilters: FilterState) => {
    setFiltersState(newFilters);
  };
  
  return [filters, setFilters];
}

/**
 * Clear all stored filters
 */
export function clearFilters(): void {
  localStorage.removeItem(FILTERS_STORAGE_KEY);
} 