// @ts-nocheck
import React, { useEffect } from 'react';
import ReactDOM from 'react-dom/client';
import { BrowserRouter, Route, Routes } from 'react-router-dom';
import App from './pages/App';
import TourDetail from './pages/TourDetail';
import Checkout from './pages/Checkout';
import MyBookings from './pages/MyBookings';
import { setupAxiosAuth, authenticateWithTelegram } from './auth';

// Setup axios with authentication
setupAxiosAuth();

// Try to authenticate immediately
authenticateWithTelegram().then(success => {
  if (success) {
    console.log('Authentication successful');
  } else {
    console.log('Authentication not available or failed');
  }
});

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