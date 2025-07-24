// @ts-nocheck
// src/pages/App.tsx
import React, { useEffect, useState, useCallback } from 'react';
import { usePersistedFilters, initialFilterState } from '../utils/store';
import { useTours } from '../api/client';
import { Tour } from '../types';
import { t } from '../i18n';
import { Layout } from '../components/Layout';
import { TourCard } from '../components/TourCard';
import { Filter, X } from 'lucide-react';
import { Button } from '../components/ui/button';
import { Skeleton } from '../components/ui/skeleton';

export default function App() {
  // Load filters from localStorage and manage state persistence
  const [appliedFilters, setAppliedFilters] = usePersistedFilters();
  // Separate state for pending filters (not yet applied)
  const [pendingFilters, setPendingFilters] = useState(appliedFilters);
  const [availableCategories, setAvailableCategories] = useState<string[]>([]);
  const [isFilterOpen, setIsFilterOpen] = useState(false);
  
  // Use React Query to fetch tours with caching - only use applied filters
  const { data: tours, isLoading, refetch } = useTours(appliedFilters);

  // Sync pending filters when applied filters change (e.g., on reset)
  useEffect(() => {
    setPendingFilters(appliedFilters);
  }, [appliedFilters]);

  useEffect(() => {
    // Extract available categories from tour data for filtering
    if (tours) {
      const uniqueCategories = new Set<string>();
      tours.forEach(tour => {
        if (tour.categories && tour.categories.length > 0) {
          tour.categories.forEach(cat => uniqueCategories.add(cat));
        } else if (tour.category) {
          uniqueCategories.add(tour.category);
        }
      });
      setAvailableCategories(Array.from(uniqueCategories));
    }
  }, [tours]);

  const handleFiltersChange = (newFilters) => {
    setPendingFilters(newFilters);
  };

  // Apply pending filters and fetch data
  const applyFilters = useCallback(() => {
    setAppliedFilters(pendingFilters);
    refetch();
    
    // Close filter drawer on mobile after applying
    if (window.innerWidth < 768) {
      setIsFilterOpen(false);
    }
  }, [pendingFilters, setAppliedFilters, refetch]);

  const resetFilters = () => {
    setAppliedFilters(initialFilterState);
    setPendingFilters(initialFilterState);
  };

  // Check if there are any active filters
  const hasActiveFilters = 
    appliedFilters.categories.length > 0 || 
    appliedFilters.priceMin || 
    appliedFilters.priceMax ||
    appliedFilters.dateFrom || 
    appliedFilters.dateTo || 
    appliedFilters.timeFrom || 
    appliedFilters.timeTo;

  const handlePriceChange = (field: 'priceMin' | 'priceMax', value: string) => {
    setPendingFilters({
      ...pendingFilters,
      [field]: value
    });
  };

  const handleDateChange = (field: 'dateFrom' | 'dateTo', value: string) => {
    setPendingFilters({
      ...pendingFilters,
      [field]: value
    });
  };

  const handleTimeChange = (field: 'timeFrom' | 'timeTo', value: string) => {
    setPendingFilters({
      ...pendingFilters,
      [field]: value
    });
  };

  const handleCategoryChange = (category: string) => {
    const newCategories = pendingFilters.categories.includes(category)
      ? pendingFilters.categories.filter(c => c !== category)
      : [...pendingFilters.categories, category];
    
    setPendingFilters({
      ...pendingFilters,
      categories: newCategories
    });
  };

  return (
    <Layout>
      <div className="space-y-6">
        {/* Header with title and filters button on the same line */}
        <div className="flex justify-between items-start">
          <h1 className="text-2xl font-bold pr-4 flex-1">{t('available_tours')}</h1>
          
          <Button 
            variant="outline" 
            size="sm"
            className="flex items-center gap-1 flex-shrink-0"
            onClick={() => setIsFilterOpen(!isFilterOpen)}
          >
            <Filter className="h-4 w-4" />
            {t('filters')}
          </Button>
        </div>
        
        {/* Active filter indicators */}
        {hasActiveFilters && (
          <div className="flex flex-wrap gap-2 mb-4">
            {appliedFilters.categories.length > 0 && (
              <div className="bg-gray-100 text-gray-800 text-xs px-2 py-1 rounded-full">
                {appliedFilters.categories.length} {t('categories')}
              </div>
            )}
            {appliedFilters.priceMin && (
              <div className="bg-gray-100 text-gray-800 text-xs px-2 py-1 rounded-full">
                {t('min')}: {appliedFilters.priceMin}
              </div>
            )}
            {appliedFilters.priceMax && (
              <div className="bg-gray-100 text-gray-800 text-xs px-2 py-1 rounded-full">
                {t('max')}: {appliedFilters.priceMax}
              </div>
            )}
            {appliedFilters.dateFrom && (
              <div className="bg-gray-100 text-gray-800 text-xs px-2 py-1 rounded-full">
                {t('from')}: {appliedFilters.dateFrom}
              </div>
            )}
            {appliedFilters.dateTo && (
              <div className="bg-gray-100 text-gray-800 text-xs px-2 py-1 rounded-full">
                {t('to')}: {appliedFilters.dateTo}
              </div>
            )}
            {appliedFilters.timeFrom && (
              <div className="bg-gray-100 text-gray-800 text-xs px-2 py-1 rounded-full">
                {t('time_from')}: {appliedFilters.timeFrom}
              </div>
            )}
            {appliedFilters.timeTo && (
              <div className="bg-gray-100 text-gray-800 text-xs px-2 py-1 rounded-full">
                {t('time_to')}: {appliedFilters.timeTo}
              </div>
            )}
          </div>
        )}
        
        <div className="flex flex-col md:flex-row gap-6">
          {/* Sidebar with filters - visible based on isFilterOpen state */}
          <div className={`
            fixed inset-y-0 right-0 w-3/4 max-w-sm bg-white shadow-lg z-50 transform transition-transform duration-300 ease-in-out
            ${isFilterOpen ? 'translate-x-0' : 'translate-x-full'}
            md:translate-x-0 md:static md:shadow-none md:w-64 md:flex-shrink-0 md:max-w-none
          `}>
            <div className="p-4 h-full overflow-auto">
              {/* Mobile header */}
              <div className="flex justify-between items-center mb-4 md:hidden">
                <h2 className="font-semibold">{t('filters')}</h2>
                <button onClick={() => setIsFilterOpen(false)} className="text-gray-500">
                  <X className="h-5 w-5" />
                </button>
              </div>
              
              {/* Filter content */}
              <div className="space-y-4">
                {/* Price range */}
                <div>
                  <h3 className="font-medium mb-2">{t('price_range')}</h3>
                  <div className="flex gap-2">
                    <input 
                      type="number" 
                      placeholder={t('min')} 
                      className="w-full p-2 border rounded-md"
                      value={pendingFilters.priceMin || ''}
                      onChange={(e) => handlePriceChange('priceMin', e.target.value)}
                    />
                    <input 
                      type="number" 
                      placeholder={t('max')} 
                      className="w-full p-2 border rounded-md"
                      value={pendingFilters.priceMax || ''}
                      onChange={(e) => handlePriceChange('priceMax', e.target.value)}
                    />
                  </div>
                </div>
                
                {/* Date range */}
                <div>
                  <h3 className="font-medium mb-2">{t('date_range')}</h3>
                  <div className="flex gap-2">
                    <input 
                      type="date" 
                      className="w-full p-2 border rounded-md"
                      value={pendingFilters.dateFrom || ''}
                      onChange={(e) => handleDateChange('dateFrom', e.target.value)}
                    />
                    <input 
                      type="date" 
                      className="w-full p-2 border rounded-md"
                      value={pendingFilters.dateTo || ''}
                      onChange={(e) => handleDateChange('dateTo', e.target.value)}
                    />
                  </div>
                </div>
                
                {/* Time range */}
                <div>
                  <h3 className="font-medium mb-2">{t('time_range')}</h3>
                  <div className="flex gap-2">
                    <input 
                      type="time" 
                      className="w-full p-2 border rounded-md"
                      value={pendingFilters.timeFrom || ''}
                      onChange={(e) => handleTimeChange('timeFrom', e.target.value)}
                    />
                    <input 
                      type="time" 
                      className="w-full p-2 border rounded-md"
                      value={pendingFilters.timeTo || ''}
                      onChange={(e) => handleTimeChange('timeTo', e.target.value)}
                    />
                  </div>
                </div>
                
                {/* Categories filter */}
                <div>
                  <h3 className="font-medium mb-2">{t('categories')}</h3>
                  <div className="max-h-48 overflow-y-auto pr-2">
                    {availableCategories.map((category, i) => (
                      <div key={i} className="flex items-center gap-2 py-1">
                        <input 
                          type="checkbox" 
                          id={`cat-${i}`} 
                          checked={pendingFilters.categories.includes(category)}
                          onChange={() => handleCategoryChange(category)}
                          className="rounded border-gray-300 text-blue-600"
                        />
                        <label 
                          htmlFor={`cat-${i}`}
                          className="flex-1 text-sm cursor-pointer"
                        >
                          {category}
                        </label>
                      </div>
                    ))}
                    {availableCategories.length === 0 && (
                      <p className="text-gray-500 text-sm">{t('no_categories')}</p>
                    )}
                  </div>
                </div>
                
                <div className="flex gap-2 mt-4">
                  <Button 
                    className="flex-1"
                    onClick={applyFilters}
                  >
                    {t('apply_filters')}
                  </Button>
                  
                  {hasActiveFilters && (
                    <Button 
                      variant="outline"
                      className="flex-1"
                      onClick={resetFilters}
                    >
                      {t('reset')}
                    </Button>
                  )}
                </div>
              </div>
            </div>
          </div>
          
          {/* Overlay when filter is open on mobile */}
          {isFilterOpen && (
            <div 
              className="fixed inset-0 bg-black/50 z-40 md:hidden" 
              onClick={() => setIsFilterOpen(false)}
            />
          )}
          
          {/* Main content area */}
          <div className="flex-1">
            {isLoading ? (
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                {[...Array(6)].map((_, index) => (
                  <Skeleton key={index} className="h-80 w-full rounded-lg" />
                ))}
              </div>
            ) : tours && tours.length > 0 ? (
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                {tours.map(tour => (
                  <TourCard key={tour.id} tour={tour} />
                ))}
              </div>
            ) : (
              <div className="bg-white rounded-xl p-8 shadow-md text-center">
                <p className="text-xl font-medium text-gray-500 mb-2">
                  {t('no_tours_found')}
                </p>
                <p className="text-gray-500">
                  {t('try_different_filters')}
                </p>
              </div>
            )}
          </div>
        </div>
      </div>
    </Layout>
  );
}