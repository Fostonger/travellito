// auth.ts - Authentication utilities for the webapp

import axios from 'axios';

// Token storage keys and settings
const ACCESS_TOKEN_KEY = 'authToken'; // Keeping original key for backward compatibility
const REFRESH_TOKEN_KEY = 'refreshToken';
const TOKEN_EXP_KEY = 'tokenExpiry';

// For debugging - set to true to enable console logs
const DEBUG = true;

// Declare global Telegram WebApp interface
declare global {
  interface Window {
    Telegram: {
      WebApp: {
        initData: string;
        initDataUnsafe: {
          user?: {
            id: number;
            first_name: string;
            last_name?: string;
            username?: string;
          };
        };
      };
    };
  }
}

// Debug logger
const log = (...args: any[]) => {
  if (DEBUG) {
    console.log('[Auth]', ...args);
  }
};

/**
 * Parse JWT token and extract payload
 */
const parseJwt = (token: string | null): any => {
  if (!token) return null;
  try {
    const base64Url = token.split('.')[1];
    const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');
    const jsonPayload = decodeURIComponent(atob(base64).split('').map(c => {
      return '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2);
    }).join(''));
    return JSON.parse(jsonPayload);
  } catch (error) {
    console.error('Error parsing JWT:', error);
    return null;
  }
};

/**
 * Get current API base URL
 */
export const getApiBaseUrl = (): string => {
  // @ts-ignore - Vite specific environment variable
  return import.meta.env?.VITE_API_BASE || 'http://localhost:8000/api/v1';
};

/**
 * Store token information in localStorage
 */
const storeTokenInfo = (token: string) => {
  if (!token) {
    log('No token provided to store');
    return;
  }
  
  // Store the access token
  localStorage.setItem(ACCESS_TOKEN_KEY, token);
  log('Access token stored in localStorage');
  
  try {
    // Parse token to get expiration
    const payload = parseJwt(token);
    if (payload && payload.exp) {
      const expiryMs = payload.exp * 1000;
      localStorage.setItem(TOKEN_EXP_KEY, expiryMs.toString());
      log(`Token expiry set: ${new Date(expiryMs).toLocaleString()}`);
    }
  } catch (err) {
    log('Error parsing token:', err);
  }
};

/**
 * Get a refresh token for the current access token
 * This function directly calls the backend to obtain a refresh token
 * for the current access token
 */
export const getRefreshToken = async (): Promise<boolean> => {
  try {
    const accessToken = localStorage.getItem(ACCESS_TOKEN_KEY);
    if (!accessToken) {
      log('No access token found, cannot get refresh token');
      return false;
    }
    
    // Get the user ID from the token
    const payload = parseJwt(accessToken);
    if (!payload || !payload.sub) {
      log('Invalid token payload, cannot get refresh token');
      return false;
    }
    
    // Directly call the bot auth endpoint which returns both tokens
    log('Calling bot auth endpoint to get refresh token');
    const apiBase = getApiBaseUrl();
    
    // Use the user ID from the token to authenticate
    const response = await axios.post(`${apiBase}/auth/telegram/bot`, {
      id: payload.sub,
      // Include minimal required fields
      first_name: payload.first || 'User',
      auth_date: Date.now()
    });
    
    log('Bot auth response:', response.status);
    
    if (response.data && response.data.refresh_token) {
      // Store the refresh token
      localStorage.setItem(REFRESH_TOKEN_KEY, response.data.refresh_token);
      log('Refresh token stored in localStorage');
      
      // Optionally update the access token if it was also returned
      if (response.data.access_token) {
        storeTokenInfo(response.data.access_token);
      }
      
      return true;
    }
    
    log('No refresh token in response');
    return false;
  } catch (error) {
    log('Error getting refresh token:', error);
    return false;
  }
};

/**
 * Check if access token is expired
 */
const isTokenExpired = (): boolean => {
  const expiry = localStorage.getItem(TOKEN_EXP_KEY);
  if (!expiry) return true;
  
  // Add 30-second buffer to ensure we refresh before actual expiry
  return Date.now() > (parseInt(expiry) - 30000);
};

/**
 * Refresh the access token
 */
export const refreshAccessToken = async (): Promise<boolean> => {
  const refreshToken = localStorage.getItem(REFRESH_TOKEN_KEY);
  log('Attempting to refresh with token:', refreshToken ? 'available' : 'missing');
  
  if (!refreshToken) {
    log('No refresh token available, attempting to obtain one');
    const gotToken = await getRefreshToken();
    if (!gotToken) {
      log('Failed to get refresh token');
      return false;
    }
  }
  
  try {
    const apiBase = getApiBaseUrl();
    const refreshToken = localStorage.getItem(REFRESH_TOKEN_KEY);
    
    // Make the refresh request
    const response = await axios.post(
      `${apiBase}/auth/refresh`, 
      { refresh_token: refreshToken },
      { headers: { 'Content-Type': 'application/json' } }
    );
    
    log('Refresh response:', response.status);
    
    if (response.data && response.data.access_token) {
      storeTokenInfo(response.data.access_token);
      
      // Update axios headers
      axios.defaults.headers.common['Authorization'] = `Bearer ${response.data.access_token}`;
      log('Token refreshed successfully');
      
      return true;
    }
    
    log('Invalid refresh response');
    return false;
  } catch (error) {
    log('Token refresh error:', error);
    
    // If we get a 401, clear the refresh token as it's invalid
    if (axios.isAxiosError(error) && error.response?.status === 401) {
      log('Refresh token is invalid, clearing');
      localStorage.removeItem(REFRESH_TOKEN_KEY);
    }
    
    return false;
  }
};

// Configure axios to include auth token in all requests
export const setupAxiosAuth = () => {
  log('Setting up axios auth interceptors');
  
  // First check URL parameters for token (highest priority)
  const urlParams = new URLSearchParams(window.location.search);
  const tokenFromUrl = urlParams.get('token');
  
  // Then check localStorage
  const tokenFromStorage = localStorage.getItem(ACCESS_TOKEN_KEY);
  
  // Use URL token if available, otherwise use stored token
  const authToken = tokenFromUrl || tokenFromStorage;
  
  if (tokenFromUrl) {
    // If token was in URL, save it to localStorage for future use
    storeTokenInfo(tokenFromUrl);
    log('Auth token saved from URL parameters');
    
    // Clean URL by removing the token parameter (for security)
    if (window.history && window.history.replaceState) {
      urlParams.delete('token');
      const newUrl = window.location.pathname + 
        (urlParams.toString() ? '?' + urlParams.toString() : '') + 
        window.location.hash;
      window.history.replaceState({}, document.title, newUrl);
    }
    
    // Try to get a refresh token for this access token
    getRefreshToken().then(success => {
      log('Refresh token acquisition:', success ? 'successful' : 'failed');
    });
  } else {
    log('No auth token in URL parameters, using stored token:', !!tokenFromStorage);
  }
  
  if (authToken) {
    axios.defaults.headers.common['Authorization'] = `Bearer ${authToken}`;
    log('Auth token set in axios defaults');
  } else {
    console.warn('No auth token available');
  }
  
  // Add response interceptor to handle 401 errors
  axios.interceptors.response.use(
    (response) => response,
    async (error) => {
      log('Axios error:', error.response?.status, error.config?.url);
      
      // Only process 401 errors (unauthorized)
      if (error.response?.status === 401 && !error.config.url.includes('/auth/refresh')) {
        log('401 error detected, attempting token refresh');
        
        // Try to refresh the token
        const refreshed = await refreshAccessToken();
        if (refreshed && error.config) {
          // Retry the original request with new token
          const newToken = localStorage.getItem(ACCESS_TOKEN_KEY);
          error.config.headers['Authorization'] = `Bearer ${newToken}`;
          return axios(error.config);
        }
        
        // If refresh failed, try to authenticate with Telegram
        log('Token refresh failed, attempting re-auth with Telegram');
        const success = await authenticateWithTelegram();
        
        if (success && error.config) {
          // Retry the original request with new token
          const newToken = localStorage.getItem(ACCESS_TOKEN_KEY);
          error.config.headers['Authorization'] = `Bearer ${newToken}`;
          return axios(error.config);
        }
      }
      
      return Promise.reject(error);
    }
  );
  
  // Add request interceptor to check token expiration before requests
  axios.interceptors.request.use(
    async (config) => {
      // Skip token refresh for refresh requests to avoid loops
      if (config.url?.includes('/auth/refresh')) {
        return config;
      }
      
      // Check if token is expired
      if (isTokenExpired()) {
        log('Token is expired, attempting refresh');
        
        const refreshed = await refreshAccessToken();
        if (refreshed) {
          // Update the Authorization header
          const newToken = localStorage.getItem(ACCESS_TOKEN_KEY);
          if (newToken) {
            config.headers.Authorization = `Bearer ${newToken}`;
          }
        }
      }
      
      return config;
    },
    (error) => Promise.reject(error)
  );
};

// Authenticate with the backend using Telegram WebApp data
export const authenticateWithTelegram = async () => {
  log('Attempting to authenticate with Telegram WebApp data');
  
  try {
    // Check if we have Telegram WebApp data
    if (window.Telegram?.WebApp?.initDataUnsafe?.user) {
      const user = window.Telegram.WebApp.initDataUnsafe.user;
      log('Found Telegram user data:', user.id, user.first_name);
      
      // Add hash from initData for verification
      const userData = {
        id: user.id,
        first_name: user.first_name,
        last_name: user.last_name,
        username: user.username,
        auth_date: Date.now(),
        hash: window.Telegram.WebApp.initData,
      };
      
      const apiBase = getApiBaseUrl();
      log('Calling auth endpoint:', `${apiBase}/auth/telegram/bot`);
      
      // Call auth endpoint
      const response = await axios.post(`${apiBase}/auth/telegram/bot`, userData);
      
      log('Auth response:', response.status);
      
      if (response.data && response.data.access_token) {
        // Store access token
        storeTokenInfo(response.data.access_token);
        
        // Store refresh token if available
        if (response.data.refresh_token) {
          localStorage.setItem(REFRESH_TOKEN_KEY, response.data.refresh_token);
          log('Refresh token stored');
        } else {
          log('No refresh token in response');
        }
        
        // Set authorization header for future requests
        axios.defaults.headers.common['Authorization'] = `Bearer ${response.data.access_token}`;
        log('Token set in axios defaults');
        
        return true;
      } else {
        log('No access token in response');
        return false;
      }
    } else {
      console.warn('No Telegram WebApp user data available');
      return false;
    }
  } catch (error) {
    console.error('Authentication error:', error);
    return false;
  }
}; 