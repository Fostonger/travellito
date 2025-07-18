// @ts-nocheck
import React from 'react';
import ReactDOM from 'react-dom/client';
import { BrowserRouter, Route, Routes } from 'react-router-dom';
import App from './pages/App';
import TourDetail from './pages/TourDetail';
import Checkout from './pages/Checkout';
import MyBookings from './pages/MyBookings';
import { setupAxiosAuth, authenticateWithTelegram } from './auth';

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

const root = ReactDOM.createRoot(document.getElementById('root') as HTMLElement);

root.render(
  <React.StrictMode>
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<App />} />
        <Route path="/tour/:id" element={<TourDetail />} />
        <Route path="/checkout" element={<Checkout />} />
        <Route path="/bookings" element={<MyBookings />} />
      </Routes>
    </BrowserRouter>
  </React.StrictMode>
); 