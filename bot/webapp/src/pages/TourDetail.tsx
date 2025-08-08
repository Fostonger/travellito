// @ts-nocheck
import React, { useState, useEffect } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { Calendar, Clock, MapPin, ChevronLeft, ChevronRight, X } from 'lucide-react';
import { t, fmtPrice } from '../i18n';
import { formatDate, formatTime, formatFullDate, getDateString, getDepartureDate } from '../utils/dateUtils';
import { useTour, useTourDepartures } from '../api/client';
import { Layout } from '../components/Layout';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { Skeleton } from '../components/ui/skeleton';
import { Tabs } from '../components/ui/tabs';

export default function TourDetail() {
  const { id } = useParams();
  const nav = useNavigate();
  
  // Use React Query for data fetching with caching
  const { data: tour, isLoading: tourLoading } = useTour(id);
  const { data: departures = [], isLoading: departuresLoading } = useTourDepartures(id);
  
  const [imgIdx, setImgIdx] = useState(0);
  const [fullscreenImg, setFullscreenImg] = useState(null);
  const [selectedDate, setSelectedDate] = useState(null);

  const loading = tourLoading || departuresLoading;

  // Set the first date as selected by default when departures load
  useEffect(() => {
    if (departures && departures.length > 0 && !selectedDate) {
      const firstDate = getDateString(departures[0].starts_at);
      setSelectedDate(firstDate);
    }
  }, [departures, selectedDate]);

  const nextImg = () => {
    if (tour?.images?.length > 0) {
      setImgIdx((imgIdx + 1) % tour.images.length);
    }
  };
  
  const prevImg = () => {
    if (tour?.images?.length > 0) {
      setImgIdx((imgIdx - 1 + tour.images.length) % tour.images.length);
    }
  };
  
  // Group departures by date
  const departuresByDate = departures.reduce((acc, dep) => {
    const dateStr = getDateString(dep.starts_at);
    if (!acc[dateStr]) acc[dateStr] = [];
    // Deduplicate by starts_at minute-level to avoid duplicates when toggling tabs
    const key = `${dep.starts_at}`;
    if (!acc[dateStr].some((d) => d.starts_at === dep.starts_at)) {
      acc[dateStr].push(dep);
    }
    // Sort by time ascending for consistent order
    acc[dateStr].sort((a, b) => new Date(a.starts_at).getTime() - new Date(b.starts_at).getTime());
    return acc;
  }, {} as Record<string, any[]>);
  
  // Get unique dates
  const uniqueDates = Object.keys(departuresByDate);

  if (loading) {
    return (
      <Layout>
        <TourDetailsSkeleton />
      </Layout>
    );
  }

  if (!tour) {
    return (
      <Layout>
        <div className="flex justify-center items-center h-64">
          <p className="text-lg">{t('not_found')}</p>
        </div>
      </Layout>
    );
  }

  // Parse price_net to number if it's a string
  const price = typeof tour.price === 'string' 
    ? parseFloat(tour.price.replace(/[^\d.-]/g, '')) 
    : tour.price;

  // Get categories (either from tour.categories array or single tour.category)
  const categories = tour.categories && tour.categories.length > 0 
    ? tour.categories 
    : tour.category 
      ? [tour.category] 
      : [];

  return (
    <Layout>
      <div className="space-y-3">
        {/* Back button */}
        <div className="flex items-center">
          <Link to="/tours">
            <Button 
              variant="ghost" 
              size="sm" 
              className="flex items-center gap-1"
            >
              <ChevronLeft className="h-4 w-4" />
              {t('back_to_tours')}
            </Button>
          </Link>
        </div>
        
        {/* Image gallery */}
        <div className="relative rounded-xl overflow-hidden h-64 md:h-96 bg-gray-100">
          {tour.images && tour.images.length > 0 ? (
            <>
              <img
                src={tour.images[imgIdx].url}
                alt={tour.title}
                className="w-full h-full object-cover"
                onClick={() => setFullscreenImg(tour.images[imgIdx].url)}
              />
              {tour.images.length > 1 && (
                <>
                  <button
                    className="absolute left-2 top-1/2 -translate-y-1/2 bg-white/80 rounded-full p-2 shadow-md"
                    onClick={prevImg}
                  >
                    <ChevronLeft className="h-5 w-5" />
                  </button>
                  <button
                    className="absolute right-2 top-1/2 -translate-y-1/2 bg-white/80 rounded-full p-2 shadow-md"
                    onClick={nextImg}
                  >
                    <ChevronRight className="h-5 w-5" />
                  </button>
                  <div className="absolute bottom-2 left-1/2 -translate-x-1/2 flex space-x-1">
                    {tour.images.map((_, idx) => (
                      <div 
                        key={idx}
                        className={`w-2 h-2 rounded-full ${idx === imgIdx ? 'bg-white' : 'bg-white/50'}`}
                        onClick={() => setImgIdx(idx)}
                      />
                    ))}
                  </div>
                </>
              )}
            </>
          ) : (
            <div className="w-full h-full flex items-center justify-center text-gray-400">
              {t('no_image')}
            </div>
          )}
        </div>

        {/* Fullscreen image modal */}
        {fullscreenImg && (
          <div 
            className="fixed inset-0 bg-black/90 z-50 flex items-center justify-center"
            onClick={() => setFullscreenImg(null)}
          >
            <img 
              src={fullscreenImg} 
              className="max-w-full max-h-full object-contain"
              alt={tour.title}
            />
            <button 
              className="absolute top-4 right-4 text-white bg-black/50 rounded-full p-2"
              onClick={() => setFullscreenImg(null)}
            >
              <X className="h-6 w-6" />
            </button>
          </div>
        )}

        {/* Tour details */}
        <div className="bg-card rounded-lg shadow-sm p-4">
          <h1 className="text-2xl font-bold mb-4">{tour.title}</h1>
          
          <div className="flex flex-wrap gap-2 mb-4">
            {categories.map((category, idx) => (
              <Badge key={idx} variant="secondary">
                {category}
              </Badge>
            ))}
          </div>
          
          <div className="space-y-3 mb-6">
            {tour.duration_minutes && (
              <div className="flex items-center text-muted-foreground">
                <Clock className="h-4 w-4 mr-2" />
                <span>
                  {Math.floor(tour.duration_minutes / 60)} {t('hours')} {tour.duration_minutes % 60} {t('minutes')}
                </span>
              </div>
            )}
            
            {tour.address && (
              <div className="flex items-start text-muted-foreground">
                <MapPin className="h-4 w-4 mr-2 mt-1" />
                <div>
                  <div className="font-medium text-foreground">{t('meeting_point')}</div>
                  <div>{tour.address}</div>
                </div>
              </div>
            )}
            
            <div className="flex items-center font-semibold text-lg">
              <span className="text-muted-foreground mr-2">{t('price')}:</span>
              <span>{fmtPrice(price)}</span>
            </div>
          </div>
          
          <div className="prose max-w-none">
            <p className="whitespace-pre-line">{tour.description}</p>
          </div>
        </div>

        {/* Departures section */}
        <div className="bg-card rounded-lg shadow-sm overflow-hidden">
          <h2 className="text-xl font-semibold p-4 border-b">
            {t('upcoming_departures')}
          </h2>
          
          {uniqueDates.length > 0 ? (
            <>
              {/* Date tabs */}
              <div className="border-b overflow-x-auto">
                <div className="flex p-2">
                  {uniqueDates.map(dateStr => (
                    <button
                      key={dateStr}
                      className={`px-4 py-2 whitespace-nowrap mx-1 rounded-md font-medium transition-colors
                        ${selectedDate === dateStr 
                          ? 'bg-primary text-primary-foreground' 
                          : 'hover:bg-accent'
                        }`}
                      onClick={() => setSelectedDate(dateStr)}
                    >
                      {formatDate(new Date(dateStr).toISOString())}
                    </button>
                  ))}
                </div>
              </div>
              
              {/* Departures for selected date */}
              {selectedDate && (
                <div className="p-6">
                  <h3 className="font-medium text-muted-foreground mb-4">
                    {formatFullDate(new Date(selectedDate).toISOString())}
                  </h3>
                  <div className="space-y-4">
                    {departuresByDate[selectedDate].map((dep) => {
                      const time = formatTime(dep.starts_at);
                      return (
                        <div key={(dep.id !== null && dep.id !== undefined) ? `id-${dep.id}` : `start-${dep.starts_at}`} className="flex justify-between items-center border-b pb-4">
                          <div>
                            <div className="font-bold">{time}</div>
                            <div className="text-sm text-muted-foreground">
                              {t('seats_left')}: {dep.seats_left}
                            </div>
                          </div>
                          <Button 
                            onClick={() => {
                              // If this is a virtual departure (no real ID yet), create a special negative ID
                              const departureData = { ...dep };
                              if (dep.is_virtual) {
                                // Parse the date string properly
                                // First, check if the date string has a timezone indicator
                                const hasTimezoneInfo = dep.starts_at.endsWith('Z') || dep.starts_at.includes('+');
                                
                                // Create timestamp that preserves the exact UTC time without double conversion
                                let timestamp;
                                if (hasTimezoneInfo) {
                                  // If it has timezone info, parse directly
                                  timestamp = new Date(dep.starts_at).getTime();
                                } else {
                                  // If no timezone info, assume it's UTC and append 'Z'
                                  timestamp = new Date(dep.starts_at + 'Z').getTime();
                                }
                                
                                // Create a simpler virtual ID format that's easier for the backend to parse
                                // Just use a negative tour ID, and pass the timestamp separately
                                const virtualId = -Math.abs(parseInt(id));
                                departureData.id = virtualId;
                                
                                // Include the full timestamp for the backend to use
                                departureData.virtual_timestamp = timestamp;
                              }
                              nav('/checkout', { state: { tourId: id, departure: departureData } });
                            }}
                            disabled={dep.seats_left <= 0}
                          >
                            {t('book')}
                          </Button>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}
            </>
          ) : (
            <div className="p-6 text-center text-muted-foreground">
              {t('no_departures')}
            </div>
          )}
        </div>
      </div>
    </Layout>
  );
}

// Loading skeleton
function TourDetailsSkeleton() {
  return (
    <div className="space-y-6">
      {/* Image skeleton */}
      <Skeleton className="w-full h-64 md:h-96 rounded-lg" />

      {/* Details skeleton */}
      <div className="bg-card rounded-lg shadow-sm p-6">
        <Skeleton className="h-8 w-3/4 mb-4" />
        <div className="flex gap-2 mb-4">
          <Skeleton className="h-6 w-20" />
          <Skeleton className="h-6 w-20" />
        </div>
        <div className="space-y-3 mb-6">
          <Skeleton className="h-4 w-40" />
          <Skeleton className="h-4 w-60" />
          <Skeleton className="h-6 w-32" />
        </div>
        <div className="space-y-2">
          <Skeleton className="h-4 w-full" />
          <Skeleton className="h-4 w-full" />
          <Skeleton className="h-4 w-3/4" />
        </div>
      </div>

      {/* Departures skeleton */}
      <div className="bg-card rounded-lg shadow-sm overflow-hidden">
        <Skeleton className="h-10 w-full" />
        <div className="border-b p-2">
          <div className="flex gap-2">
            <Skeleton className="h-10 w-24" />
            <Skeleton className="h-10 w-24" />
          </div>
        </div>
        <div className="p-6">
          <Skeleton className="h-6 w-40 mb-4" />
          <div className="space-y-4">
            <div className="flex justify-between items-center pb-4">
              <div>
                <Skeleton className="h-6 w-20 mb-1" />
                <Skeleton className="h-4 w-28" />
              </div>
              <Skeleton className="h-10 w-24" />
            </div>
            <div className="flex justify-between items-center pb-4">
              <div>
                <Skeleton className="h-6 w-20 mb-1" />
                <Skeleton className="h-4 w-28" />
              </div>
              <Skeleton className="h-10 w-24" />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
} 
