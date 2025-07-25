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
import TelegramDebug from './components/TelegramDebug';
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

// Add Telegram WebApp script to the document head
const addTelegramScript = () => {
  const script = document.createElement('script');
  script.src = 'https://telegram.org/js/telegram-web-app.js';
  script.async = true;
  document.head.appendChild(script);
};

// Initialize application
const initialize = async () => {
  // First add the Telegram WebApp script
  addTelegramScript();
  
  // Initialize analytics (which sets up global interceptors)
  initAnalytics();
  
  // Then set up authentication flow
  setupAxiosAuth();
};

// Run initialization
initialize();

// Root component to handle Telegram WebApp initialization
const Root = () => {
  useEffect(() => {
    // Signal to Telegram that we're ready when component mounts
    if (window.Telegram?.WebApp?.ready) {
      window.Telegram.WebApp.ready();
      
      // Try to authenticate with Telegram after ready
      setTimeout(async () => {
        try {
          await authenticateWithTelegram();
        } catch (error) {
          // Silent fail - auth will be retried on API calls if needed
        }
      }, 100);
    }
  }, []);

  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <ScrollRestoration />
        <Routes>
          <Route path="/" element={<Navigate to="/tours" replace />} />
          <Route path="/tours" element={<App />} />
          <Route path="/tour/:id" element={<TourDetail />} />
          <Route path="/checkout" element={<Checkout />} />
          <Route path="/bookings" element={<MyBookings />} />
          <Route path="/debug" element={<TelegramDebug />} />
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