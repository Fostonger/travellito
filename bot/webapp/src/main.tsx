// @ts-nocheck
import React from 'react';
import ReactDOM from 'react-dom/client';
import { BrowserRouter, Route, Routes, Navigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import App from './pages/App';
import TourDetail from './pages/TourDetail';
import Checkout from './pages/Checkout';
import MyBookings from './pages/MyBookings';
import ScrollRestoration from './components/ScrollRestoration';
import { setupAxiosAuth, authenticateWithTelegram } from './auth';
import { initAnalytics } from './utils/analytics';
import './index.css';

// Create a client
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 5 * 60 * 1000, // 5 minutes
      cacheTime: 30 * 60 * 1000, // 30 minutes
      refetchOnWindowFocus: false,
    },
  },
});

// Initialize application
const initialize = async () => {
  // First initialize analytics (which sets up global interceptors)
  initAnalytics();
  
  // Then set up authentication flow
  setupAxiosAuth();
  
  // Add a small delay to let setupAxiosAuth process URL params
  setTimeout(async () => {
    try {
      // Try to authenticate with Telegram
      await authenticateWithTelegram();
    } catch (error) {
      // Silent fail - auth will be retried on API calls if needed
    }
  }, 500);
};

initialize();

// Render the application
ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <ScrollRestoration />
        <Routes>
          <Route path="/" element={<Navigate to="/tours" replace />} />
          <Route path="/tours" element={<App />} />
          <Route path="/tour/:id" element={<TourDetail />} />
          <Route path="/checkout" element={<Checkout />} />
          <Route path="/bookings" element={<MyBookings />} />
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  </React.StrictMode>
); 