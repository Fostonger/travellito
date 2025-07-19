// @ts-nocheck
import React, { useState } from 'react';
import { useParams, Link, useNavigate } from 'react-router-dom';
import { t, fmtPrice } from '../i18n';
import { formatDate, formatTime, formatFullDate, getDateString, getDepartureDate } from '../utils/dateUtils';
import { useTour, useTourDepartures } from '../api/client';
import { Skeleton } from '../components/ui/skeleton';

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
  React.useEffect(() => {
    if (departures && departures.length > 0 && !selectedDate) {
      const firstDate = getDateString(departures[0].starts_at);
      setSelectedDate(firstDate);
    }
  }, [departures, selectedDate]);

  const nextImg = () => setImgIdx((imgIdx + 1) % (tour.images?.length || 1));
  const prevImg = () => setImgIdx((imgIdx - 1 + (tour.images?.length || 1)) % (tour.images?.length || 1));
  
  // Group departures by date
  const departuresByDate = departures.reduce((acc, dep) => {
    const dateStr = getDateString(dep.starts_at);
    if (!acc[dateStr]) acc[dateStr] = [];
    acc[dateStr].push(dep);
    return acc;
  }, {});
  
  // Get unique dates
  const uniqueDates = Object.keys(departuresByDate);

  if (loading) {
    return <TourDetailSkeleton />;
  }

  if (!tour) return <p className="flex justify-center items-center h-screen text-lg">{t('not_found')}</p>;

  return (
    <div className="p-4 pb-20 bg-gray-50 min-h-screen">
      {/* Back link */}
      <div className="mb-2">
        <Link to="/" className="text-blue-600 font-medium flex items-center">
          <span className="mr-1">←</span> {t('back')}
        </Link>
      </div>

      {/* Image carousel */}
      {tour.images?.length > 0 && (
        <div className="relative mb-4 rounded-xl overflow-hidden shadow-lg">
          <img
            src={tour.images[imgIdx].url}
            className="w-full h-72 object-cover cursor-pointer"
            onClick={() => setFullscreenImg(tour.images[imgIdx].url)}
            loading="lazy" // Add lazy loading
          />
          {tour.images.length > 1 && (
            <>
              <button
                className="absolute left-2 top-1/2 -translate-y-1/2 bg-white/80 rounded-full p-2 shadow-md"
                onClick={prevImg}
              >◀</button>
              <button
                className="absolute right-2 top-1/2 -translate-y-1/2 bg-white/80 rounded-full p-2 shadow-md"
                onClick={nextImg}
              >▶</button>
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
        </div>
      )}

      {/* Fullscreen image modal */}
      {fullscreenImg && (
        <div 
          className="fixed inset-0 bg-black/90 z-50 flex items-center justify-center"
          onClick={() => setFullscreenImg(null)}
        >
          <img 
            src={fullscreenImg} 
            className="max-w-full max-h-full object-contain"
          />
          <button 
            className="absolute top-4 right-4 text-white text-2xl"
            onClick={() => setFullscreenImg(null)}
          >
            ✕
          </button>
        </div>
      )}

      {/* Tour details */}
      <div className="bg-white rounded-xl p-4 shadow-md mb-4">
        <h2 className="text-2xl font-bold mb-1">{tour.title}</h2>
        <div className="flex items-center justify-between mb-3">
          <div className="flex flex-wrap gap-1">
            {tour.categories && tour.categories.length > 0 ? (
              // Show all categories in the detail page
              tour.categories.map((category, idx) => (
                <span
                  key={idx}
                  className="inline-block px-3 py-1 text-sm rounded-full font-medium"
                  style={{ backgroundColor: pastelColor(category), color: '#333' }}
                >
                  {category}
                </span>
              ))
            ) : tour.category ? (
              // Fallback to legacy category
              <span
                className="inline-block px-3 py-1 text-sm rounded-full font-medium"
                style={{ backgroundColor: pastelColor(tour.category), color: '#333' }}
              >
                {tour.category}
              </span>
            ) : null}
          </div>
          <div className="text-xl font-bold text-blue-600">
            {fmtPrice(tour.price)}
          </div>
        </div>

        {tour.duration_minutes && (
          <div className="mb-3 flex items-center text-gray-600">
            <span className="mr-1">⏱</span>
            <span>{Math.floor(tour.duration_minutes / 60)} {t('hours')} {tour.duration_minutes % 60} {t('minutes')}</span>
          </div>
        )}
        
        <p className="mb-4 text-gray-700 whitespace-pre-line leading-relaxed">{tour.description}</p>
      </div>

      {/* Departures section with date tabs */}
      {uniqueDates.length > 0 ? (
        <div className="bg-white rounded-xl shadow-md overflow-hidden">
          <h3 className="text-xl font-semibold p-4 border-b">{t('upcoming_departures')}</h3>
          
          {/* Date tabs */}
          <div className="flex overflow-x-auto p-2 bg-gray-50">
            {uniqueDates.map(dateStr => (
              <button
                key={dateStr}
                className={`px-4 py-2 whitespace-nowrap mx-1 rounded-lg font-medium ${
                  selectedDate === dateStr 
                    ? 'bg-blue-600 text-white' 
                    : 'bg-white text-gray-700 border'
                }`}
                onClick={() => setSelectedDate(dateStr)}
              >
                {formatDate(new Date(dateStr).toISOString())}
              </button>
            ))}
          </div>
          
          {/* Departures for selected date */}
          {selectedDate && (
            <div className="p-4">
              <h4 className="font-medium text-gray-500 mb-3">
                {formatFullDate(new Date(selectedDate).toISOString())}
              </h4>
              <div className="space-y-3">
                {departuresByDate[selectedDate].map((d) => {
                  // Use the formatTime utility for consistent time display
                  const time = formatTime(d.starts_at);
                  return (
                    <div key={d.id} className="flex justify-between items-center border-b pb-3">
                      <div>
                        <div className="font-bold">{time}</div>
                        <div className="text-sm text-gray-600">{t('seats_left')}: {d.seats_left}</div>
                      </div>
                      <button 
                        onClick={() => {
                          // If this is a virtual departure (no real ID yet), create a special negative ID
                          const departureData = { ...d };
                          if (d.is_virtual) {
                            // Parse the date string properly
                            // First, check if the date string has a timezone indicator
                            const hasTimezoneInfo = d.starts_at.endsWith('Z') || d.starts_at.includes('+');
                            
                            // Create timestamp that preserves the exact UTC time without double conversion
                            let timestamp;
                            if (hasTimezoneInfo) {
                              // If it has timezone info, parse directly
                              timestamp = new Date(d.starts_at).getTime();
                            } else {
                              // If no timezone info, assume it's UTC and append 'Z'
                              timestamp = new Date(d.starts_at + 'Z').getTime();
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
                        className="px-4 py-2 bg-blue-600 text-white rounded-lg"
                        disabled={d.seats_left <= 0}
                      >
                        {t('book')}
                      </button>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </div>
      ) : (
        <div className="bg-white rounded-xl p-4 shadow-md text-center">
          <p className="text-gray-500">{t('no_departures')}</p>
        </div>
      )}
    </div>
  );
}

// Loading skeleton
function TourDetailSkeleton() {
  return (
    <div className="p-4 pb-20 bg-gray-50 min-h-screen">
      {/* Back link skeleton */}
      <div className="mb-2">
        <Skeleton className="h-6 w-20" />
      </div>

      {/* Image skeleton */}
      <Skeleton className="w-full h-72 rounded-xl mb-4" />

      {/* Details skeleton */}
      <div className="bg-white rounded-xl p-4 shadow-md mb-4">
        <Skeleton className="h-8 w-3/4 mb-2" />
        <div className="flex flex-wrap gap-1 mb-3">
          <Skeleton className="h-6 w-20" />
          <Skeleton className="h-6 w-20" />
        </div>
        <Skeleton className="h-4 w-full mb-2" />
        <Skeleton className="h-4 w-full mb-2" />
        <Skeleton className="h-4 w-3/4" />
      </div>

      {/* Departures skeleton */}
      <div className="bg-white rounded-xl shadow-md overflow-hidden">
        <Skeleton className="h-10 w-full" />
        <div className="flex gap-2 p-2 bg-gray-50">
          <Skeleton className="h-10 w-24" />
          <Skeleton className="h-10 w-24" />
        </div>
        <div className="p-4">
          <Skeleton className="h-6 w-40 mb-4" />
          <div className="space-y-4">
            <div className="flex justify-between items-center">
              <div>
                <Skeleton className="h-6 w-20 mb-1" />
                <Skeleton className="h-4 w-28" />
              </div>
              <Skeleton className="h-10 w-24" />
            </div>
            <div className="flex justify-between items-center">
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

function pastelColor(str: string): string {
  // Generate a consistent pastel color based on the string
  let hash = 0;
  for (let i = 0; i < str.length; i++) {
    hash = str.charCodeAt(i) + ((hash << 5) - hash);
  }
  const h = Math.abs(hash) % 360;
  return `hsl(${h}, 70%, 90%)`;
} 