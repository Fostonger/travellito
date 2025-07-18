// @ts-nocheck
import React, { useEffect } from 'react';
import ReactDOM from 'react-dom/client';
import { BrowserRouter, Route, Routes } from 'react-router-dom';
import App from './pages/App';
import TourDetail from './pages/TourDetail';
import Checkout from './pages/Checkout';
import MyBookings from './pages/MyBookings';
import { setupAxiosAuth, authenticateWithTelegram } from './auth';
import DebugPanel from './components/DebugPanel';

// Setup global authentication flow
const initializeAuth = async () => {
  if (window.debugLog) {
    window.debugLog("Auth initialization started");
    
    // Log what's already in localStorage
    const existingAccessToken = localStorage.getItem('authToken');
    const existingRefreshToken = localStorage.getItem('refreshToken');
    const existingUserId = localStorage.getItem('telegramUserId');
    
    window.debugLog(`Initial state - Access token: ${existingAccessToken ? 'present' : 'missing'}, ` +
                    `Refresh token: ${existingRefreshToken ? 'present' : 'missing'}, ` + 
                    `Telegram ID: ${existingUserId || 'unknown'}`);
  }
  
  // First set up axios interceptors (which also gets tokens from URL)
  setupAxiosAuth();
  
  // Add a small delay to let setupAxiosAuth process URL params
  setTimeout(async () => {
    try {
      // Try to authenticate with Telegram
      const authSuccess = await authenticateWithTelegram();
      
      // Double-check and report the final state
      if (window.debugLog) {
        const hasAccessToken = !!localStorage.getItem('authToken');
        const hasRefreshToken = !!localStorage.getItem('refreshToken');
        
        window.debugLog(`Auth ${authSuccess ? 'successful' : 'failed'}`);
        window.debugLog(`Final state - Access token: ${hasAccessToken ? 'present' : 'missing'}, ` +
                        `Refresh token: ${hasRefreshToken ? 'present' : 'missing'}`);
        
        // If we still have no refresh token, report it clearly
        if (hasAccessToken && !hasRefreshToken) {
          window.debugLog("WARNING: Access token present but refresh token missing!");
        }
      }
    } catch (error: any) {
      if (window.debugLog) {
        window.debugLog(`Auth error: ${error.message}`);
      }
    }
  }, 500); // Small delay to ensure URL params are processed
};

// Start auth initialization process
initializeAuth();

const root = ReactDOM.createRoot(document.getElementById('root') as HTMLElement);

root.render(
  <React.StrictMode>
    <BrowserRouter>
      <>
        <Routes>
          <Route path="/" element={<App />} />
          <Route path="/tour/:id" element={<TourDetail />} />
          <Route path="/checkout" element={<Checkout />} />
          <Route path="/bookings" element={<MyBookings />} />
        </Routes>
        <DebugPanel />
      </>
    </BrowserRouter>
  </React.StrictMode>
); 