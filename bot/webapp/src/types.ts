/**
 * Common types used throughout the application
 */

export interface Tour {
  id: number;
  title: string;
  price_raw?: string;
  price_net: string;
  description?: string;
  duration_minutes?: number;
  category?: string;
  categories?: string[];
  images?: TourImage[];
  address?: string;  // Add address field for departure info
}

export interface TourImage {
  url: string;
  description?: string;
}

export interface Departure {
  id: number;
  tour_id: number;
  starts_at: string;
  seats_left: number;
  is_virtual?: boolean;
  virtual_timestamp?: number;
} 