// @ts-nocheck
import React from 'react';
import ReactDOM from 'react-dom/client';
import { BrowserRouter, Route, Routes } from 'react-router-dom';
import App from './pages/App';
import TourDetail from './pages/TourDetail';
import Checkout from './pages/Checkout';
import MyBookings from './pages/MyBookings';

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