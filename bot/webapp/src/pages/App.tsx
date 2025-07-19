// @ts-nocheck
// src/pages/App.tsx
import React, { useEffect, useState, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { t, fmtPrice } from '../i18n';
import { Button } from '../components/ui/button';
import { Card } from '../components/ui/card';
import { Skeleton } from '../components/ui/skeleton';
import { ScrollArea } from '../components/ui/scroll-area';
import { Separator } from '../components/ui/separator';
import { Badge } from '../components/ui/badge';
import { usePersistedFilters, initialFilterState } from '../utils/store';
import { useTours } from '../api/client';
import { Tour } from '../types';

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

  const handleFilterChange = (key: keyof typeof pendingFilters, value: any) => {
    setPendingFilters({
      ...pendingFilters,
      [key]: value
    });
  };

  const toggleCategory = (category: string) => {
    setPendingFilters({
      ...pendingFilters,
      categories: pendingFilters.categories.includes(category)
        ? pendingFilters.categories.filter(cat => cat !== category)
        : [...pendingFilters.categories, category]
    });
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

  // Check if there are any active applied filters
  const hasActiveFilters = appliedFilters.categories.length > 0 || 
                          appliedFilters.priceMin || 
                          appliedFilters.priceMax ||
                          appliedFilters.dateFrom || 
                          appliedFilters.dateTo || 
                          appliedFilters.timeFrom || 
                          appliedFilters.timeTo;

  if (isLoading) {
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
            </div>
            
            {/* Reset filters button */}
            {hasActiveFilters && (
              <Button 
                variant="ghost" 
                size="sm"
                className="text-gray-500 hover:text-gray-700"
                onClick={resetFilters}
              >
                {t('reset')}
              </Button>
            )}
          </div>
          
          {/* Active filter indicators - now displayed on multiple lines */}
          {hasActiveFilters && (
            <div className="flex flex-wrap gap-2 mb-4">
              {appliedFilters.categories.length > 0 && (
                <Badge variant="outline" className="whitespace-nowrap">
                  {appliedFilters.categories.length} {t('categories')}
                </Badge>
              )}
              {appliedFilters.priceMin && (
                <Badge variant="outline" className="whitespace-nowrap">
                  {t('min')}: {appliedFilters.priceMin}
                </Badge>
              )}
              {appliedFilters.priceMax && (
                <Badge variant="outline" className="whitespace-nowrap">
                  {t('max')}: {appliedFilters.priceMax}
                </Badge>
              )}
              {appliedFilters.dateFrom && (
                <Badge variant="outline" className="whitespace-nowrap">
                  {t('from')}: {appliedFilters.dateFrom}
                </Badge>
              )}
              {appliedFilters.dateTo && (
                <Badge variant="outline" className="whitespace-nowrap">
                  {t('to')}: {appliedFilters.dateTo}
                </Badge>
              )}
              {appliedFilters.timeFrom && (
                <Badge variant="outline" className="whitespace-nowrap">
                  {t('time_from')}: {appliedFilters.timeFrom}
                </Badge>
              )}
              {appliedFilters.timeTo && (
                <Badge variant="outline" className="whitespace-nowrap">
                  {t('time_to')}: {appliedFilters.timeTo}
                </Badge>
              )}
            </div>
          )}
        </div>
        
        {/* Filters and results layout */}
        <div className="flex flex-col md:flex-row gap-6">
          {/* Filter panel (sidebar on desktop, drawer on mobile) */}
          <div
            className={`
              w-full md:w-64 md:flex-shrink-0 
              ${isFilterOpen ? 'block' : 'hidden md:block'}
              bg-white rounded-xl shadow-md p-4 
              max-h-screen md:sticky md:top-4
            `}
          >
            <div className="flex justify-between items-center mb-4 md:hidden">
              <h2 className="font-bold">{t('filters')}</h2>
              <button 
                className="text-gray-500"
                onClick={() => setIsFilterOpen(false)}
              >
                <CloseIcon className="h-5 w-5" />
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
                    value={pendingFilters.priceMin}
                    onChange={(e) => handleFilterChange('priceMin', e.target.value)}
                  />
                  <input 
                    type="number" 
                    placeholder={t('max')} 
                    className="w-full p-2 border rounded-md"
                    value={pendingFilters.priceMax}
                    onChange={(e) => handleFilterChange('priceMax', e.target.value)}
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
                    value={pendingFilters.dateFrom}
                    onChange={(e) => handleFilterChange('dateFrom', e.target.value)}
                  />
                  <input 
                    type="date" 
                    className="w-full p-2 border rounded-md"
                    value={pendingFilters.dateTo}
                    onChange={(e) => handleFilterChange('dateTo', e.target.value)}
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
                    value={pendingFilters.timeFrom}
                    onChange={(e) => handleFilterChange('timeFrom', e.target.value)}
                  />
                  <input 
                    type="time" 
                    className="w-full p-2 border rounded-md"
                    value={pendingFilters.timeTo}
                    onChange={(e) => handleFilterChange('timeTo', e.target.value)}
                  />
                </div>
              </div>
              
              {/* Categories filter */}
              <div>
                <h3 className="font-medium mb-2">{t('categories')}</h3>
                <ScrollArea className="h-48">
                  {availableCategories.map((category, i) => (
                    <div key={i} className="flex items-center gap-2 py-1">
                      <input 
                        type="checkbox" 
                        id={`cat-${i}`} 
                        checked={pendingFilters.categories.includes(category)}
                        onChange={() => toggleCategory(category)}
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
                </ScrollArea>
              </div>
              
              <Button 
                className="w-full bg-blue-600 hover:bg-blue-700 mt-2"
                onClick={applyFilters}
              >
                {t('apply_filters')}
              </Button>
            </div>
          </div>
          
          {/* Results grid */}
          <div className="flex-1">
            {tours && tours.length > 0 ? (
              <div className="grid gap-4 grid-cols-1 sm:grid-cols-2 lg:grid-cols-2 xl:grid-cols-3">
                {tours.map((tour) => (
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
    </div>
  );
}

// Tour card component
function TourCard({ tour }) {
  // Use the first image URL from the API response if available
  const imageUrl = tour.images && tour.images.length > 0 && tour.images[0].url;
  
  return (
    <Link to={`/tour/${tour.id}`} className="block">
      <Card className="overflow-hidden hover:shadow-xl transition-shadow">
        <div className="h-48 bg-gray-200 relative">
          {imageUrl ? (
            <img 
              src={imageUrl} 
              className="w-full h-full object-cover"
              loading="lazy"
              alt={tour.title}
              onError={(e) => {
                console.error(`Failed to load image: ${imageUrl}`);
                e.target.onerror = null;
                e.target.src = 'data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" width="100%" height="100%" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect><circle cx="8.5" cy="8.5" r="1.5"></circle><polyline points="21 15 16 10 5 21"></polyline></svg>';
              }}
            />
          ) : (
            <div className="w-full h-full flex items-center justify-center text-gray-400">
              {t('no_image')}
            </div>
          )}
        </div>
        
        <div className="p-4">
          <div className="flex flex-wrap gap-1 mb-2">
            {tour.categories && tour.categories.length > 0 ? (
              // Show up to 2 categories on the card
              tour.categories.slice(0, 2).map((category, idx) => (
                <span
                  key={idx}
                  className="inline-block px-2 py-1 text-xs rounded-full font-medium"
                  style={{ backgroundColor: pastelColor(category), color: '#333' }}
                >
                  {category}
                </span>
              ))
            ) : tour.category ? (
              // Fallback to legacy category
              <span
                className="inline-block px-2 py-1 text-xs rounded-full font-medium"
                style={{ backgroundColor: pastelColor(tour.category), color: '#333' }}
              >
                {tour.category}
              </span>
            ) : null}
            
            {/* Show +N more if there are additional categories */}
            {tour.categories && tour.categories.length > 2 && (
              <span className="inline-block px-2 py-1 text-xs bg-gray-100 rounded-full">
                +{tour.categories.length - 2}
              </span>
            )}
          </div>
          
          <h3 className="font-bold mb-1 line-clamp-2">{tour.title}</h3>
          
          <div className="mt-2">
            <span className="text-blue-600 font-bold">
              {fmtPrice(tour.price_net)}
            </span>
          </div>
        </div>
      </Card>
    </Link>
  );
}

function pastelColor(str: string): string {
  // Generate a consistent pastel color based on the string
  let hash = 0;
  for (let i = 0; i < str.length; i++) {
    hash = str.charCodeAt(i) + ((hash << 5) - hash);
  }
  const h = Math.abs(hash) % 360;
  return `hsl(${h}, 70%, 90%)`;
}

function FilterIcon({ className }: { className?: string }) {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3"></polygon>
    </svg>
  );
}

function CloseIcon({ className }: { className?: string }) {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <line x1="18" y1="6" x2="6" y2="18"></line>
      <line x1="6" y1="6" x2="18" y2="18"></line>
    </svg>
  );
}