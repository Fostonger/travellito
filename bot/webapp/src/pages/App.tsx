// @ts-nocheck
// src/pages/App.tsx
import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import axios from 'axios';
import { t, fmtPrice } from '../i18n';
import { refreshAccessToken, getRefreshToken, getApiBaseUrl } from '../auth';

interface Tour {
  id: number;
  title: string;
  price_net: string;
  category?: string;
  categories?: string[];
}

// Token status component to display token refresh functionality
function TokenStatus() {
  const [tokenExpiry, setTokenExpiry] = useState<string>('Loading...');
  const [timeLeft, setTimeLeft] = useState<number | null>(null);
  const [refreshing, setRefreshing] = useState<boolean>(false);
  const [logs, setLogs] = useState<string[]>([]);
  const [hasRefreshToken, setHasRefreshToken] = useState<boolean>(false);
  const [apiBaseUrl, setApiBaseUrl] = useState<string>('');
  const [apiCallResult, setApiCallResult] = useState<string | null>(null);
  const [telegramUserId, setTelegramUserId] = useState<string>('Unknown');
  
  // Add a log entry
  const addLog = (message: string) => {
    setLogs(prev => {
      const newLogs = [...prev, `${new Date().toLocaleTimeString()}: ${message}`];
      // Keep only the latest 10 logs
      return newLogs.slice(-10);
    });
  };

  // Parse JWT token and get expiry
  const getTokenInfo = () => {
    try {
      const storedExpiry = localStorage.getItem('tokenExpiry');
      const accessToken = localStorage.getItem('authToken');
      const refreshToken = localStorage.getItem('refreshToken');
      const userIdFromStorage = localStorage.getItem('telegramUserId');
      
      setHasRefreshToken(!!refreshToken);
      setApiBaseUrl(getApiBaseUrl());
      setTelegramUserId(userIdFromStorage || 'Unknown');
      
      if (storedExpiry) {
        const expiryDate = new Date(parseInt(storedExpiry));
        setTokenExpiry(expiryDate.toLocaleTimeString());
        
        const left = Math.max(0, parseInt(storedExpiry) - Date.now());
        setTimeLeft(Math.round(left / 1000));
      } else if (accessToken) {
        // Try to extract from token
        try {
          const base64Url = accessToken.split('.')[1];
          const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');
          const payload = JSON.parse(atob(base64));
          
          if (payload.exp) {
            const expiryMs = payload.exp * 1000;
            setTokenExpiry(new Date(expiryMs).toLocaleTimeString());
            setTimeLeft(Math.round((expiryMs - Date.now()) / 1000));
          } else {
            setTokenExpiry('Unknown');
            setTimeLeft(null);
          }
        } catch (e) {
          setTokenExpiry('Invalid token');
          setTimeLeft(null);
        }
      } else {
        setTokenExpiry('No token');
        setTimeLeft(null);
      }
    } catch (e) {
      console.error('Error getting token info:', e);
      setTokenExpiry('Error');
      setTimeLeft(null);
    }
  };

  // Get a refresh token
  const handleGetRefreshToken = async () => {
    setRefreshing(true);
    addLog('Getting refresh token');
    setApiCallResult('Getting refresh token...');
    
    try {
      const success = await getRefreshToken();
      
      if (success) {
        addLog('Successfully obtained refresh token');
        setApiCallResult('Successfully obtained refresh token');
      } else {
        addLog('Failed to get refresh token');
        setApiCallResult('Failed to get refresh token');
      }
    } catch (error) {
      addLog(`Error: ${error.message}`);
      setApiCallResult(`Error: ${error.message}`);
    } finally {
      setRefreshing(false);
      getTokenInfo();
    }
  };

  // Refresh token handler
  const handleRefresh = async () => {
    setRefreshing(true);
    addLog('Manual token refresh requested');
    setApiCallResult('Refreshing token...');
    
    try {
      const success = await refreshAccessToken();
      addLog(`Refresh ${success ? 'succeeded' : 'failed'}`);
      
      if (success) {
        const newExpiry = localStorage.getItem('tokenExpiry');
        if (newExpiry) {
          addLog(`New expiry set: ${new Date(parseInt(newExpiry)).toLocaleTimeString()}`);
        }
        setApiCallResult('Token refreshed successfully');
      } else {
        setApiCallResult('Token refresh failed');
      }
    } catch (error) {
      addLog(`Refresh error: ${error.message || 'unknown error'}`);
      setApiCallResult(`Error: ${error.message}`);
    } finally {
      setRefreshing(false);
      getTokenInfo();
    }
  };

  // Make a test API call
  const handleTestCall = async () => {
    try {
      addLog('Making test API call...');
      setApiCallResult('Testing...');
      
      const apiBase = getApiBaseUrl();
      const response = await axios.get(`${apiBase}/auth/me`);
      
      const result = JSON.stringify(response.data, null, 2);
      addLog(`API call success`);
      setApiCallResult(`Success: ${result}`);
    } catch (error) {
      const errorMessage = error.response?.data?.detail || error.message || 'Unknown error';
      addLog(`API call failed: ${errorMessage}`);
      setApiCallResult(`Failed: ${errorMessage}`);
      console.error('Test API call error:', error);
    } finally {
      getTokenInfo();
    }
  };

  // Clear all tokens
  const handleClearTokens = () => {
    localStorage.removeItem('authToken');
    localStorage.removeItem('refreshToken');
    localStorage.removeItem('tokenExpiry');
    localStorage.removeItem('telegramUserId');
    addLog('All tokens cleared');
    setApiCallResult('Tokens cleared');
    getTokenInfo();
  };

  // Update status regularly
  useEffect(() => {
    getTokenInfo();
    const interval = setInterval(getTokenInfo, 1000);
    
    // Add initial log
    addLog('Token status initialized');
    
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="fixed bottom-4 right-4 bg-white p-3 rounded-lg shadow-lg border border-cyan-200 text-sm max-w-xs z-50">
      <h3 className="font-bold text-cyan-800 mb-1">Token Status</h3>
      
      <div className="mb-3">
        <p className="mb-1">API Base: <span className="font-mono text-xs">{apiBaseUrl}</span></p>
        <p className="mb-1">Telegram ID: <span className="font-mono text-xs">{telegramUserId}</span></p>
        <p className="mb-1">Expires: <span className="font-mono">{tokenExpiry}</span></p>
        {timeLeft !== null && (
          <p className="mb-1">
            Time left: <span className={timeLeft < 5 ? 'text-red-500 font-bold' : ''}>{timeLeft}s</span>
          </p>
        )}
        <p className="mb-1">
          Refresh token: {hasRefreshToken ? 
            <span className="text-green-500">Available</span> : 
            <span className="text-red-500">Missing</span>}
        </p>
      </div>
      
      <div className="flex flex-wrap gap-2 mb-3">
        {!hasRefreshToken && (
          <button 
            onClick={handleGetRefreshToken}
            disabled={refreshing}
            className={`px-2 py-1 rounded text-xs ${
              refreshing 
                ? 'bg-gray-200 text-gray-500' 
                : 'bg-blue-600 text-white hover:bg-blue-700'
            }`}
          >
            {refreshing ? 'Getting...' : 'Get Refresh Token'}
          </button>
        )}
        
        <button 
          onClick={handleRefresh}
          disabled={refreshing}
          className={`px-2 py-1 rounded text-xs ${
            refreshing 
              ? 'bg-gray-200 text-gray-500' 
              : 'bg-cyan-600 text-white hover:bg-cyan-700'
          }`}
        >
          {refreshing ? 'Refreshing...' : 'Refresh Token'}
        </button>
        <button
          onClick={handleTestCall}
          className="px-2 py-1 rounded text-xs bg-green-600 text-white hover:bg-green-700"
        >
          Test API
        </button>
        <button
          onClick={handleClearTokens}
          className="px-2 py-1 rounded text-xs bg-red-600 text-white hover:bg-red-700"
        >
          Clear All
        </button>
      </div>
      
      {apiCallResult && (
        <div className="mb-3">
          <h4 className="font-bold text-xs mb-1">Result:</h4>
          <div className="bg-gray-100 p-1 rounded text-xs max-h-20 overflow-y-auto">
            <pre className="whitespace-pre-wrap break-all font-mono text-[10px]">{apiCallResult}</pre>
          </div>
        </div>
      )}
      
      <div>
        <h4 className="font-bold text-xs mb-1">Logs:</h4>
        <div className="bg-gray-100 p-1 rounded text-xs h-24 overflow-y-auto">
          {logs.map((log, i) => (
            <div key={i} className="mb-1 font-mono text-[10px]">{log}</div>
          ))}
        </div>
      </div>
    </div>
  );
}

export default function App() {
  const [tours, setTours] = useState<Tour[]>([]);
  const [loading, setLoading] = useState(true);
  const apiBase =
    import.meta.env.VITE_API_BASE || 'https://api.trycloudflare.com/api/v1';

  useEffect(() => {
    (async () => {
      try {
        const { data } = await axios.get(`${apiBase}/public/tours/search`, {
          params: { limit: 50 },
          withCredentials: true,
        });
        setTours(data);
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen">
        <span className="animate-pulse text-gray-400">{t('loading')}</span>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 p-4">
      <h1 className="text-2xl font-extrabold text-cyan-700 mb-4">
        {t('available_tours')}
      </h1>

      {tours.length === 0 && (
        <p className="text-gray-500">{t('no_tours')}</p>
      )}

      <div className="grid gap-4 sm:grid-cols-2">
        {tours.map((tour) => (
          <Link
            key={tour.id}
            to={`/tour/${tour.id}`}
            className="block rounded-xl shadow hover:shadow-md transition bg-white"
          >
            <div className="p-4">
              <h2 className="font-semibold text-lg mb-2">{tour.title}</h2>
              <div className="flex flex-wrap gap-1 mb-2">
                {tour.categories && tour.categories.length > 0 ? (
                  // Show up to 3 categories with the new design
                  tour.categories.slice(0, 3).map((category, idx) => (
                    <span
                      key={idx}
                      className="inline-block px-2 py-0.5 text-xs rounded-full"
                      style={{ backgroundColor: pastelColor(category), color: '#333' }}
                    >
                      {category}
                    </span>
                  ))
                ) : tour.category ? (
                  // Fallback to legacy category
                  <span
                    className="inline-block px-2 py-0.5 text-xs rounded-full"
                    style={{ backgroundColor: pastelColor(tour.category), color: '#333' }}
                  >
                    {tour.category}
                  </span>
                ) : null}
                {tour.categories && tour.categories.length > 3 && (
                  <span className="inline-block px-2 py-0.5 text-xs rounded-full bg-gray-100 text-gray-500">
                    +{tour.categories.length - 3}
                  </span>
                )}
              </div>
              <p className="text-cyan-700 font-bold">
                {fmtPrice(tour.price_net)}
              </p>
            </div>
          </Link>
        ))}
      </div>

      <div className="mt-8">
        <Link
          to="/bookings"
          className="text-cyan-600 underline hover:text-cyan-800"
        >
          {t('my_bookings')}
        </Link>
      </div>
      
      {/* Token refresh status */}
      <TokenStatus />
    </div>
  );
}

// Simple deterministic pastel color generator from string
function pastelColor(str: string): string {
  let hash = 0;
  for (let i = 0; i < str.length; i++) hash = str.charCodeAt(i) + ((hash << 5) - hash);
  const h = hash % 360;
  return `hsl(${h}, 70%, 85%)`;
}