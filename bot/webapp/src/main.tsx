// @ts-nocheck
import React from 'react';
import ReactDOM from 'react-dom/client';
import { BrowserRouter, Route, Routes } from 'react-router-dom';
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

// Initialize analytics
initAnalytics();

// Setup authentication flow
const initializeAuth = async () => {
  // Set up axios interceptors (which also gets tokens from URL)
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

// Start auth initialization process
initializeAuth();

// Register service worker for caching
if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/sw.js').catch(error => {
      console.log('Service worker registration failed:', error);
    });
  });
}

const root = ReactDOM.createRoot(document.getElementById('root') as HTMLElement);

root.render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <ScrollRestoration />
        <Routes>
          <Route path="/" element={<App />} />
          <Route path="/tour/:id" element={<TourDetail />} />
          <Route path="/checkout" element={<Checkout />} />
          <Route path="/bookings" element={<MyBookings />} />
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  </React.StrictMode>
); 