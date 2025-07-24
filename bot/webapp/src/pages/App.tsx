// @ts-nocheck
// src/pages/App.tsx
import React, { useEffect, useState, useCallback } from 'react';
import { usePersistedFilters, initialFilterState } from '../utils/store';
import { useTours } from '../api/client';
import { Tour } from '../types';
import { t } from '../i18n';
import { Layout } from '../components/Layout';
import { TourCard } from '../components/TourCard';
import { TourFilters } from '../components/TourFilters';
import { Skeleton } from '../components/ui/skeleton';

export default function App() {
  // Load filters from localStorage and manage state persistence
  const [appliedFilters, setAppliedFilters] = usePersistedFilters();
  // Separate state for pending filters (not yet applied)
  const [pendingFilters, setPendingFilters] = useState(appliedFilters);
  const [availableCategories, setAvailableCategories] = useState<string[]>([]);
  
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
  }, [pendingFilters, setAppliedFilters, refetch]);

  const resetFilters = () => {
    setAppliedFilters(initialFilterState);
    setPendingFilters(initialFilterState);
  };

  return (
    <Layout>
      <div className="space-y-6">
        <h1 className="text-2xl font-bold">{t('available_tours')}</h1>
        
        <div className="flex flex-col md:flex-row gap-6">
          {/* Sidebar with filters */}
          <div className="w-full md:w-64 md:flex-shrink-0">
            <TourFilters
              filters={pendingFilters}
              availableCategories={availableCategories}
              onFiltersChange={handleFiltersChange}
              onApply={applyFilters}
              onReset={resetFilters}
            />
          </div>
          
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