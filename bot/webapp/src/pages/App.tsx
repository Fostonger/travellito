// @ts-nocheck
// src/pages/App.tsx
import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import axios from 'axios';
import { t, fmtPrice } from '../i18n';
import { Button } from '../components/ui/button';
import { Card } from '../components/ui/card';
import { Skeleton } from '../components/ui/skeleton';
import { ScrollArea } from '../components/ui/scroll-area';
import { Separator } from '../components/ui/separator';
import { Badge } from '../components/ui/badge';

interface Tour {
  id: number;
  title: string;
  price_net: string;
  category?: string;
  categories?: string[];
}

interface FilterState {
  categories: string[];
  priceMin: string;
  priceMax: string;
  dateFrom: string;
  dateTo: string;
  timeFrom: string;
  timeTo: string;
}

const initialFilterState: FilterState = {
  categories: [],
  priceMin: '',
  priceMax: '',
  dateFrom: '',
  dateTo: '',
  timeFrom: '',
  timeTo: ''
};

export default function App() {
  const [tours, setTours] = useState<Tour[]>([]);
  const [loading, setLoading] = useState(true);
  const [filters, setFilters] = useState<FilterState>(initialFilterState);
  const [availableCategories, setAvailableCategories] = useState<string[]>([]);
  const [isFilterOpen, setIsFilterOpen] = useState(false);
  
  const apiBase =
    import.meta.env.VITE_API_BASE || 'https://api.trycloudflare.com/api/v1';

  useEffect(() => {
    fetchTours();
  }, []);

  const fetchTours = async (appliedFilters = {}) => {
    setLoading(true);
    try {
      // Fix for handling array parameters
      const params: Record<string, any> = {
        limit: 50,
        ...appliedFilters
      };
      
      // Use axios.getUri to create a custom URL with properly formatted parameters
      // This ensures arrays are sent correctly as separate parameters with the same name
      let url = `${apiBase}/public/tours/search`;
      const queryParams = new URLSearchParams();
      
      // Add each parameter to the URL, handling arrays specially
      Object.entries(params).forEach(([key, value]) => {
        if (Array.isArray(value)) {
          // For arrays like categories, add multiple parameters with the same name
          value.forEach(item => {
            queryParams.append(key, item);
          });
        } else if (value !== undefined && value !== null && value !== '') {
          queryParams.append(key, value);
        }
      });
      
      // Append the query string to the URL
      const queryString = queryParams.toString();
      if (queryString) {
        url += `?${queryString}`;
      }
      
      // Make the request with the custom URL
      const { data } = await axios.get(url, { withCredentials: true });
      setTours(data);
      
      // Extract all unique categories for filters
      const uniqueCategories = new Set<string>();
      data.forEach(tour => {
        if (tour.categories && tour.categories.length > 0) {
          tour.categories.forEach(cat => uniqueCategories.add(cat));
        } else if (tour.category) {
          uniqueCategories.add(tour.category);
        }
      });
      setAvailableCategories(Array.from(uniqueCategories));
    } finally {
      setLoading(false);
    }
  };

  const handleFilterChange = (key: keyof FilterState, value: any) => {
    setFilters(prev => ({
      ...prev,
      [key]: value
    }));
  };

  const toggleCategory = (category: string) => {
    setFilters(prev => {
      const updatedCategories = prev.categories.includes(category)
        ? prev.categories.filter(cat => cat !== category)
        : [...prev.categories, category];
        
      return {
        ...prev,
        categories: updatedCategories
      };
    });
  };

  // Time filter handling to fix timezone format
  const applyFilters = () => {
    const appliedFilters: Record<string, any> = {};
    
    // Apply price range
    if (filters.priceMin) appliedFilters.price_min = filters.priceMin;
    if (filters.priceMax) appliedFilters.price_max = filters.priceMax;
    
    // Apply date range
    if (filters.dateFrom) appliedFilters.date_from = filters.dateFrom;
    if (filters.dateTo) appliedFilters.date_to = filters.dateTo;
    
    // Apply time range with timezone offset
    if (filters.timeFrom) {
      // Get timezone offset in format +HH:MM or -HH:MM
      const date = new Date();
      const offsetMinutes = date.getTimezoneOffset();
      const offsetHours = Math.floor(Math.abs(offsetMinutes) / 60);
      const offsetMins = Math.abs(offsetMinutes) % 60;
      
      // Format as +HH:MM or -HH:MM (note: getTimezoneOffset returns inverse sign)
      const offsetSign = offsetMinutes > 0 ? '-' : '+';
      const offsetFormatted = `${offsetSign}${String(offsetHours).padStart(2, '0')}:${String(offsetMins).padStart(2, '0')}`;
      
      // Combine time with timezone offset
      appliedFilters.time_from = `${filters.timeFrom}${offsetFormatted}`;
    }
    
    if (filters.timeTo) {
      // Get timezone offset in format +HH:MM or -HH:MM
      const date = new Date();
      const offsetMinutes = date.getTimezoneOffset();
      const offsetHours = Math.floor(Math.abs(offsetMinutes) / 60);
      const offsetMins = Math.abs(offsetMinutes) % 60;
      
      // Format as +HH:MM or -HH:MM (note: getTimezoneOffset returns inverse sign)
      const offsetSign = offsetMinutes > 0 ? '-' : '+';
      const offsetFormatted = `${offsetSign}${String(offsetHours).padStart(2, '0')}:${String(offsetMins).padStart(2, '0')}`;
      
      // Combine time with timezone offset
      appliedFilters.time_to = `${filters.timeTo}${offsetFormatted}`;
    }
    
    // Apply category filtering (handled by backend now)
    if (filters.categories.length > 0) {
      appliedFilters.categories = filters.categories;
    }
    
    fetchTours(appliedFilters);
    
    // Close filter drawer on mobile after applying
    if (window.innerWidth < 768) {
      setIsFilterOpen(false);
    }
  };

  const resetFilters = () => {
    setFilters(initialFilterState);
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50">
        <div className="container mx-auto px-4 py-6">
          {/* Header with skeleton */}
          <header className="flex flex-wrap justify-between items-center mb-6">
            <h1 className="text-2xl font-extrabold text-cyan-700">
              {t('available_tours')}
            </h1>
            <Skeleton className="h-10 w-32" />
          </header>
          
          <div className="grid gap-4 grid-cols-1 sm:grid-cols-2 lg:grid-cols-3">
            {[...Array(6)].map((_, index) => (
              <Skeleton key={index} className="h-48 w-full rounded-xl" />
            ))}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="container mx-auto px-4 py-6">
        {/* Header with title and My Bookings button */}
        <header className="flex flex-wrap justify-between items-center mb-6">
          <h1 className="text-2xl font-extrabold text-cyan-700 mb-2 sm:mb-0">
            {t('available_tours')}
          </h1>
          <Link to="/bookings">
            <Button className="bg-cyan-700 hover:bg-cyan-800 text-white">
              {t('my_bookings')}
            </Button>
          </Link>
        </header>
        
        {/* Mobile-friendly filter bar */}
        <div className="sticky top-0 z-10 bg-gray-50 pb-4">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <Button 
                variant="outline" 
                size="sm"
                className="flex items-center gap-1"
                onClick={() => setIsFilterOpen(!isFilterOpen)}
              >
                <FilterIcon className="h-4 w-4" />
                {t('filters')}
              </Button>
              
              {/* Active filter indicators */}
              <div className="flex gap-1 overflow-x-auto hide-scrollbar">
                {filters.categories.length > 0 && (
                  <Badge variant="outline" className="whitespace-nowrap">
                    {filters.categories.length} {t('categories')}
                  </Badge>
                )}
                {filters.priceMin && (
                  <Badge variant="outline" className="whitespace-nowrap">
                    {t('min')}: {filters.priceMin}
                  </Badge>
                )}
                {filters.priceMax && (
                  <Badge variant="outline" className="whitespace-nowrap">
                    {t('max')}: {filters.priceMax}
                  </Badge>
                )}
                {filters.dateFrom && (
                  <Badge variant="outline" className="whitespace-nowrap">
                    {t('from')}: {filters.dateFrom}
                  </Badge>
                )}
                {(filters.priceMin || filters.priceMax || filters.dateFrom || filters.dateTo || 
                  filters.timeFrom || filters.timeTo || filters.categories.length > 0) && (
                  <Button 
                    variant="ghost" 
                    size="sm" 
                    className="h-6 px-2 text-xs"
                    onClick={resetFilters}
                  >
                    {t('clear')}
                  </Button>
                )}
              </div>
            </div>
            <div className="text-sm text-gray-500">
              {tours.length} {t('tours')}
            </div>
          </div>
        </div>
        
        {/* Mobile Filter Drawer */}
        <div className={`
          fixed inset-0 bg-black/50 z-20 transition-opacity 
          ${isFilterOpen ? 'opacity-100' : 'opacity-0 pointer-events-none'}
        `} onClick={() => setIsFilterOpen(false)}>
          <div 
            className={`
              fixed bottom-0 left-0 right-0 max-h-[85vh] bg-white rounded-t-xl 
              transition-transform duration-300 p-4 overflow-auto
              ${isFilterOpen ? 'translate-y-0' : 'translate-y-full'}
            `}
            onClick={e => e.stopPropagation()}
          >
            <div className="flex justify-between items-center mb-4">
              <h2 className="font-semibold text-lg">{t('filter_tours')}</h2>
              <button 
                className="p-1 rounded-full hover:bg-gray-100"
                onClick={() => setIsFilterOpen(false)}
              >
                <CloseIcon className="h-5 w-5" />
              </button>
            </div>
            
            <div className="space-y-4">
              {/* Categories filter */}
              <div>
                <h3 className="font-medium mb-2 text-sm text-gray-700">
                  {t('categories')}
                </h3>
                <ScrollArea className="h-24">
                  <div className="flex flex-wrap gap-2">
                    {availableCategories.map((category) => (
                      <button
                        key={category}
                        onClick={() => toggleCategory(category)}
                        className={`inline-block px-3 py-1 text-xs rounded-full transition ${
                          filters.categories.includes(category)
                            ? 'bg-cyan-600 text-white'
                            : 'bg-gray-100 text-gray-800 hover:bg-gray-200'
                        }`}
                      >
                        {category}
                      </button>
                    ))}
                  </div>
                </ScrollArea>
              </div>
              
              <Separator />
              
              {/* Price range filter */}
              <div>
                <h3 className="font-medium mb-2 text-sm text-gray-700">
                  {t('price_range')}
                </h3>
                <div className="flex items-center gap-2">
                  <input
                    type="number"
                    placeholder={t('min')}
                    className="p-2 border rounded flex-1 text-sm"
                    value={filters.priceMin}
                    onChange={(e) => handleFilterChange('priceMin', e.target.value)}
                  />
                  <span>-</span>
                  <input
                    type="number"
                    placeholder={t('max')}
                    className="p-2 border rounded flex-1 text-sm"
                    value={filters.priceMax}
                    onChange={(e) => handleFilterChange('priceMax', e.target.value)}
                  />
                </div>
              </div>
              
              <Separator />
              
              {/* Date range filter */}
              <div>
                <h3 className="font-medium mb-2 text-sm text-gray-700">
                  {t('date_range')}
                </h3>
                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <label className="block text-xs mb-1 text-gray-500">{t('from')}</label>
                    <input
                      type="date"
                      className="p-2 border rounded w-full text-sm"
                      value={filters.dateFrom}
                      onChange={(e) => handleFilterChange('dateFrom', e.target.value)}
                    />
                  </div>
                  <div>
                    <label className="block text-xs mb-1 text-gray-500">{t('to')}</label>
                    <input
                      type="date"
                      className="p-2 border rounded w-full text-sm"
                      value={filters.dateTo}
                      onChange={(e) => handleFilterChange('dateTo', e.target.value)}
                    />
                  </div>
                </div>
              </div>
              
              <Separator />
              
              {/* Time range filter */}
              <div>
                <h3 className="font-medium mb-2 text-sm text-gray-700">
                  {t('time_range')}
                </h3>
                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <label className="block text-xs mb-1 text-gray-500">{t('from')}</label>
                    <input
                      type="time"
                      className="p-2 border rounded w-full text-sm"
                      value={filters.timeFrom}
                      onChange={(e) => handleFilterChange('timeFrom', e.target.value)}
                    />
                  </div>
                  <div>
                    <label className="block text-xs mb-1 text-gray-500">{t('to')}</label>
                    <input
                      type="time"
                      className="p-2 border rounded w-full text-sm"
                      value={filters.timeTo}
                      onChange={(e) => handleFilterChange('timeTo', e.target.value)}
                    />
                  </div>
                </div>
              </div>
              
              {/* Action buttons */}
              <div className="pt-4 flex gap-3">
                <Button 
                  variant="outline" 
                  className="flex-1" 
                  onClick={resetFilters}
                >
                  {t('reset')}
                </Button>
                <Button 
                  className="flex-1 bg-cyan-700 hover:bg-cyan-800"
                  onClick={applyFilters}
                >
                  {t('apply')}
                </Button>
              </div>
            </div>
          </div>
        </div>
        
        {/* Tour Results */}
        {tours.length === 0 && (
          <div className="flex flex-col items-center justify-center py-12">
            <p className="text-gray-500 mb-4">{t('no_tours')}</p>
            <Button variant="outline" onClick={resetFilters}>
              {t('clear_filters')}
            </Button>
          </div>
        )}

        <div className="grid gap-4 grid-cols-1 sm:grid-cols-2 lg:grid-cols-3">
          {tours.map((tour) => (
            <Link
              key={tour.id}
              to={`/tour/${tour.id}`}
              className="block rounded-xl shadow-sm hover:shadow-md transition bg-white overflow-hidden"
            >
              <div className="p-4">
                <h2 className="font-semibold text-lg mb-2 line-clamp-2">{tour.title}</h2>
                <div className="flex flex-wrap gap-1 mb-3">
                  {tour.categories && tour.categories.length > 0 ? (
                    // Show up to 3 categories with the new design
                    tour.categories.slice(0, 3).map((category, idx) => (
                      <span
                        key={idx}
                        className="inline-block px-2 py-0.5 text-xs rounded-full"
                        style={{ backgroundColor: pastelColor(category), color: '#333' }}
                      >
                        {category}
                      </span>
                    ))
                  ) : tour.category ? (
                    // Fallback to legacy category
                    <span
                      className="inline-block px-2 py-0.5 text-xs rounded-full"
                      style={{ backgroundColor: pastelColor(tour.category), color: '#333' }}
                    >
                      {tour.category}
                    </span>
                  ) : null}
                  {tour.categories && tour.categories.length > 3 && (
                    <span className="inline-block px-2 py-0.5 text-xs rounded-full bg-gray-100 text-gray-500">
                      +{tour.categories.length - 3}
                    </span>
                  )}
                </div>
                <p className="text-cyan-700 font-bold">
                  {fmtPrice(tour.price_net)}
                </p>
              </div>
            </Link>
          ))}
        </div>
      </div>
    </div>
  );
}

// Simple deterministic pastel color generator from string
function pastelColor(str: string): string {
  let hash = 0;
  for (let i = 0; i < str.length; i++) hash = str.charCodeAt(i) + ((hash << 5) - hash);
  const h = hash % 360;
  return `hsl(${h}, 70%, 85%)`;
}

// SVG Icons
function FilterIcon({ className }: { className?: string }) {
  return (
    <svg 
      xmlns="http://www.w3.org/2000/svg" 
      className={className} 
      fill="none" 
      viewBox="0 0 24 24" 
      stroke="currentColor"
    >
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 4a1 1 0 011-1h16a1 1 0 011 1v2.586a1 1 0 01-.293.707l-6.414 6.414a1 1 0 00-.293.707V17l-4 4v-6.586a1 1 0 00-.293-.707L3.293 7.293A1 1 0 013 6.586V4z" />
    </svg>
  );
}

function CloseIcon({ className }: { className?: string }) {
  return (
    <svg 
      xmlns="http://www.w3.org/2000/svg" 
      className={className} 
      fill="none" 
      viewBox="0 0 24 24" 
      stroke="currentColor"
    >
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
    </svg>
  );
}