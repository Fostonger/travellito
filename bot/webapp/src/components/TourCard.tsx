import React from 'react';
import { Link } from 'react-router-dom';
import { MapPin, Users } from 'lucide-react';
import { Tour } from '../types';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { t, fmtPrice } from '../i18n';

interface TourCardProps {
  tour: Tour;
}

export const TourCard = ({ tour }: TourCardProps) => {
  // Get the image URL from the tour data
  const imageUrl = tour.images && tour.images.length > 0 ? tour.images[0].url : null;
  
  // Get categories (either from tour.categories array or single tour.category)
  const categories = tour.categories && tour.categories.length > 0 
    ? tour.categories 
    : tour.category 
      ? [tour.category] 
      : [];

  // Parse price_net to number if it's a string
  const price = typeof tour.price_net === 'string' 
    ? parseFloat(tour.price_net.replace(/[^\d.-]/g, '')) 
    : tour.price_net;

  return (
    <div className="bg-card rounded-lg shadow-card hover:shadow-card-hover transition-all duration-300">
      <div className="relative">
        {imageUrl ? (
          <img
            src={imageUrl}
            alt={tour.title}
            className="w-full h-48 object-cover rounded-t-lg"
            loading="lazy"
            onError={(e) => {
              e.currentTarget.onerror = null;
              e.currentTarget.src = 'data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" width="100%" height="100%" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect><circle cx="8.5" cy="8.5" r="1.5"></circle><polyline points="21 15 16 10 5 21"></polyline></svg>';
            }}
          />
        ) : (
          <div className="w-full h-48 bg-gray-200 rounded-t-lg flex items-center justify-center text-gray-400">
            {t('no_image')}
          </div>
        )}
      </div>
      
      <div className="p-4">
        <div className="flex flex-wrap gap-1 mb-2">
          {categories.slice(0, 2).map((category, index) => (
            <Badge key={index} variant="secondary" className="text-xs">
              {category}
            </Badge>
          ))}
          
          {/* Show +N more if there are additional categories */}
          {categories.length > 2 && (
            <Badge variant="outline" className="text-xs">
              +{categories.length - 2}
            </Badge>
          )}
        </div>
        
        <h3 className="font-semibold text-lg mb-2 line-clamp-2">
          {tour.title}
        </h3>
        
        {tour.address && (
          <div className="flex items-center text-muted-foreground text-sm mb-3">
            <MapPin className="h-4 w-4 mr-1" />
            <span className="truncate">{tour.address}</span>
          </div>
        )}
        
        <div className="flex items-center justify-between">
          <div className="text-lg font-semibold">
            {fmtPrice(price)}
          </div>
          <Link to={`/tour/${tour.id}`}>
            <Button size="sm">
              {t('details')}
            </Button>
          </Link>
        </div>
      </div>
    </div>
  );
}; 