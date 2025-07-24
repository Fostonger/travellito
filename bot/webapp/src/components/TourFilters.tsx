import React, { useState } from 'react';
import { Filter, X } from 'lucide-react';
import { Button } from '../components/ui/button';
import { t } from '../i18n';
import { initialFilterState } from '../utils/store';

interface TourFiltersProps {
  filters: any;
  availableCategories: string[];
  onFiltersChange: (filters: any) => void;
  onApply: () => void;
  onReset: () => void;
}

export const TourFilters = ({ 
  filters, 
  availableCategories, 
  onFiltersChange, 
  onApply, 
  onReset 
}: TourFiltersProps) => {
  const [isOpen, setIsOpen] = useState(false);
  
  const handlePriceChange = (field: 'priceMin' | 'priceMax', value: string) => {
    onFiltersChange({
      ...filters,
      [field]: value
    });
  };

  const handleDateChange = (field: 'dateFrom' | 'dateTo', value: string) => {
    onFiltersChange({
      ...filters,
      [field]: value
    });
  };

  const handleTimeChange = (field: 'timeFrom' | 'timeTo', value: string) => {
    onFiltersChange({
      ...filters,
      [field]: value
    });
  };

  const handleCategoryChange = (category: string) => {
    const newCategories = filters.categories.includes(category)
      ? filters.categories.filter(c => c !== category)
      : [...filters.categories, category];
    
    onFiltersChange({
      ...filters,
      categories: newCategories
    });
  };

  // Check if there are any active filters
  const hasActiveFilters = 
    filters.categories.length > 0 || 
    filters.priceMin || 
    filters.priceMax ||
    filters.dateFrom || 
    filters.dateTo || 
    filters.timeFrom || 
    filters.timeTo;

  return (
    <div>
      {/* Filter button and active filter indicators */}
      <div className="sticky top-0 z-10 bg-gray-50 pb-4">
        <div className="flex items-center justify-between mb-4">
          <Button 
            variant="outline" 
            size="sm"
            className="flex items-center gap-1"
            onClick={() => setIsOpen(!isOpen)}
          >
            <Filter className="h-4 w-4" />
            {t('filters')}
          </Button>
          
          {/* Reset filters button */}
          {hasActiveFilters && (
            <Button 
              variant="ghost" 
              size="sm"
              className="text-gray-500 hover:text-gray-700"
              onClick={onReset}
            >
              {t('reset')}
            </Button>
          )}
        </div>
        
        {/* Active filter indicators */}
        {hasActiveFilters && (
          <div className="flex flex-wrap gap-2 mb-4">
            {filters.categories.length > 0 && (
              <div className="bg-gray-100 text-gray-800 text-xs px-2 py-1 rounded-full">
                {filters.categories.length} {t('categories')}
              </div>
            )}
            {filters.priceMin && (
              <div className="bg-gray-100 text-gray-800 text-xs px-2 py-1 rounded-full">
                {t('min')}: {filters.priceMin}
              </div>
            )}
            {filters.priceMax && (
              <div className="bg-gray-100 text-gray-800 text-xs px-2 py-1 rounded-full">
                {t('max')}: {filters.priceMax}
              </div>
            )}
            {filters.dateFrom && (
              <div className="bg-gray-100 text-gray-800 text-xs px-2 py-1 rounded-full">
                {t('from')}: {filters.dateFrom}
              </div>
            )}
            {filters.dateTo && (
              <div className="bg-gray-100 text-gray-800 text-xs px-2 py-1 rounded-full">
                {t('to')}: {filters.dateTo}
              </div>
            )}
            {filters.timeFrom && (
              <div className="bg-gray-100 text-gray-800 text-xs px-2 py-1 rounded-full">
                {t('time_from')}: {filters.timeFrom}
              </div>
            )}
            {filters.timeTo && (
              <div className="bg-gray-100 text-gray-800 text-xs px-2 py-1 rounded-full">
                {t('time_to')}: {filters.timeTo}
              </div>
            )}
          </div>
        )}
      </div>
      
      {/* Filter panel */}
      {isOpen && (
        <div className="fixed inset-0 bg-black/50 z-50 md:hidden" onClick={() => setIsOpen(false)} />
      )}
      
      <div className={`
        fixed inset-y-0 right-0 w-3/4 max-w-sm bg-white shadow-lg z-50 transform transition-transform duration-300 ease-in-out
        ${isOpen ? 'translate-x-0' : 'translate-x-full'}
        md:translate-x-0 md:static md:shadow-none md:w-full md:max-w-none md:bg-transparent
      `}>
        <div className="p-4 md:p-0">
          {/* Mobile header */}
          <div className="flex justify-between items-center mb-4 md:hidden">
            <h2 className="font-semibold">{t('filters')}</h2>
            <button onClick={() => setIsOpen(false)} className="text-gray-500">
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
                  value={filters.priceMin || ''}
                  onChange={(e) => handlePriceChange('priceMin', e.target.value)}
                />
                <input 
                  type="number" 
                  placeholder={t('max')} 
                  className="w-full p-2 border rounded-md"
                  value={filters.priceMax || ''}
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
                  value={filters.dateFrom || ''}
                  onChange={(e) => handleDateChange('dateFrom', e.target.value)}
                />
                <input 
                  type="date" 
                  className="w-full p-2 border rounded-md"
                  value={filters.dateTo || ''}
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
                  value={filters.timeFrom || ''}
                  onChange={(e) => handleTimeChange('timeFrom', e.target.value)}
                />
                <input 
                  type="time" 
                  className="w-full p-2 border rounded-md"
                  value={filters.timeTo || ''}
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
                      checked={filters.categories.includes(category)}
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
            
            <Button 
              className="w-full bg-blue-600 hover:bg-blue-700 mt-2"
              onClick={() => {
                onApply();
                setIsOpen(false);
              }}
            >
              {t('apply_filters')}
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}; 