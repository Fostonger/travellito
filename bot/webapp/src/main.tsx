// @ts-nocheck
import React, { useEffect } from 'react';
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
  console.log('[Main] Starting initialization');
  console.log('[Main] WebApp available:', !!window.Telegram?.WebApp);
  
  // Initialize analytics (which sets up global interceptors)
  initAnalytics();
  
  // Then set up authentication flow
  setupAxiosAuth();
  
  // Try to authenticate immediately if WebApp is available
  if (window.Telegram?.WebApp) {
    try {
      console.log('[Main] Attempting immediate authentication');
      await authenticateWithTelegram();
    } catch (error) {
      console.error('[Main] Initial auth failed:', error);
      // Silent fail - auth will be retried on API calls if needed
    }
  } else {
    console.warn('[Main] Telegram WebApp not available at initialization');
  }
};

// Run initialization
initialize();

// Root component to handle Telegram WebApp initialization
const Root = () => {
  useEffect(() => {
    // Double-check WebApp is ready (in case it wasn't available during initialize)
    if (window.Telegram?.WebApp?.ready && !window.TelegramWebAppReady) {
      window.Telegram.WebApp.ready();
      window.TelegramWebAppReady = true;
      console.log('[Root] Called WebApp.ready() from React');
    }
  }, []);

  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <ScrollRestoration />
        <Routes>
          <Route path="/" element={<Navigate to={`/tours${location.search}`} replace />} />
          <Route path="/tours" element={<App />} />
          <Route path="/tour/:id" element={<TourDetail />} />
          <Route path="/checkout" element={<Checkout />} />
          <Route path="/bookings" element={<MyBookings />} />
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  );
};

// Render the application
ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <Root />
  </React.StrictMode>
); 