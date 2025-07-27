// auth.ts - Authentication utilities for the webapp

import axios from 'axios';
import { getClientId } from './utils/analytics';

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
            language_code?: string;
          };
          start_param?: string;
        };
        showAlert: (message: string) => void;
        ready: () => void;
        platform: string;
      };
    };
  }
}

// Token storage keys
const ACCESS_TOKEN_KEY = 'access_token';
const REFRESH_TOKEN_KEY = 'refresh_token';

// Silent logger - does nothing in production
const log = (...args: any[]) => {
  // No logging in production
};

/**
 * Get current API base URL
 */
export const getApiBaseUrl = (): string => {
  // @ts-ignore - Vite specific environment variable
  return import.meta.env?.VITE_API_BASE || 'http://localhost:8000/api/v1';
};

/**
 * Store authentication tokens in localStorage
 */
export const storeTokens = (accessToken: string, refreshToken: string): void => {
  localStorage.setItem(ACCESS_TOKEN_KEY, accessToken);
  localStorage.setItem(REFRESH_TOKEN_KEY, refreshToken);
};

/**
 * Get access token from localStorage
 */
export const getAccessToken = (): string | null => {
  return localStorage.getItem(ACCESS_TOKEN_KEY);
};

/**
 * Get refresh token from localStorage
 */
export const getRefreshToken = (): string | null => {
  return localStorage.getItem(REFRESH_TOKEN_KEY);
};

/**
 * Clear authentication tokens from localStorage
 */
export const clearTokens = (): void => {
  localStorage.removeItem(ACCESS_TOKEN_KEY);
  localStorage.removeItem(REFRESH_TOKEN_KEY);
};

/**
 * Safe wrapper to get initData from Telegram WebApp
 */
export function getInitDataSafely(): { ok: boolean; initData?: string; reason?: 'not-telegram' | 'empty-initdata' } {
  const tg = window.Telegram?.WebApp;
  if (!tg) return { ok: false, reason: 'not-telegram' };

  const initData: string = tg.initData || '';
  if (!initData.length) return { ok: false, reason: 'empty-initdata' };

  return { ok: true, initData };
}

/**
 * Check if the app is running inside Telegram WebApp
 */
export const isRunningInTelegram = (): boolean => {
  return !!window.Telegram?.WebApp;
};

/**
 * Authenticate with the backend using Telegram WebApp initData
 */
export const authenticateWithTelegram = async (): Promise<boolean> => {
  try {
    // Signal to Telegram that we're ready
    const tg = window.Telegram?.WebApp;
    tg?.ready?.();

    // Get initData safely
    const initDataResult = getInitDataSafely();
    if (!initDataResult.ok) {
      console.error(`Telegram WebApp authentication failed: ${initDataResult.reason}`);
      return false;
    }

    // Log the initData (for debugging, but don't log the whole thing for security)
    const initData = initDataResult.initData;
    if (initData && initData.length > 20) {
      console.log(`Using initData: ${initData.substring(0, 10)}...${initData.substring(initData.length - 10)}`);
    }

    // Log user info from initDataUnsafe (safe to log)
    if (tg?.initDataUnsafe?.user) {
      console.log('User from initDataUnsafe:', {
        id: tg.initDataUnsafe.user.id,
        username: tg.initDataUnsafe.user.username,
        first_name: tg.initDataUnsafe.user.first_name,
      });
    }

    // Log start_param if available
    if (tg?.initDataUnsafe?.start_param) {
      console.log('Start param:', tg.initDataUnsafe.start_param);
    }

    const apiBase = getApiBaseUrl();
    
    try {
      const response = await axios.post(
        `${apiBase}/auth/telegram/init`, 
        { init_data: initDataResult.initData },
        { timeout: 10000 } // 10 second timeout
      );
      
      // Check if authentication was successful
      if (response.data && response.data.user) {
        console.log('Authentication successful:', response.data.user);
        
        // Store tokens in localStorage
        if (response.data.access_token && response.data.refresh_token) {
          storeTokens(response.data.access_token, response.data.refresh_token);
        }
        
        return true;
      }
      
      console.error('Authentication failed: Invalid response format');
      return false;
    } catch (apiError: any) {
      console.error('Authentication API error:', apiError.response?.data || apiError.message);
      return false;
    }
  } catch (error) {
    console.error('Telegram WebApp authentication error:', error);
    return false;
  }
};

/**
 * Refresh the access token using the refresh token
 */
export const refreshAccessToken = async (): Promise<boolean> => {
  try {
    const refreshToken = getRefreshToken();
    if (!refreshToken) {
      console.error('No refresh token available');
      return false;
    }
    
    const apiBase = getApiBaseUrl();
    const response = await axios.post(
      `${apiBase}/auth/refresh`,
      { refresh_token: refreshToken }
    );
    
    if (response.data && response.data.access_token) {
      // Update only the access token
      storeTokens(response.data.access_token, refreshToken);
      return true;
    }
    
    return false;
  } catch (error) {
    console.error('Failed to refresh token:', error);
    return false;
  }
};

/**
 * Check if the user is authenticated by making a test request
 */
export const checkAuthentication = async (): Promise<boolean> => {
  try {
    const apiBase = getApiBaseUrl();
    await axios.get(`${apiBase}/auth/me`);
    return true;
  } catch (error) {
    return false;
  }
};

/**
 * Log out the current user
 */
export const logout = async (): Promise<boolean> => {
  try {
    const apiBase = getApiBaseUrl();
    await axios.post(`${apiBase}/auth/logout`, {});
    
    // Clear tokens from localStorage
    clearTokens();
    
    return true;
  } catch (error) {
    // Still clear tokens even if the API call fails
    clearTokens();
    return false;
  }
};

/**
 * Configure axios to include auth token and handle 401 errors
 */
export const setupAxiosAuth = () => {
  // Remove withCredentials default since we're using token auth
  axios.defaults.withCredentials = false;
  
  // Add auth token and client ID to all requests
  axios.interceptors.request.use(async (config) => {
    // Add access token if available
    const token = getAccessToken();
    if (token) {
      config.headers['Authorization'] = `Bearer ${token}`;
    }
    
    // Add client ID header
    try {
      const clientId = await getClientId();
      if (clientId) {
        config.headers['X-Client-Id'] = clientId;
      }
    } catch (error) {
      // Silent fail
    }
    
    return config;
  });
  
  // Add response interceptor to handle 401 errors
  axios.interceptors.response.use(
    (response) => response,
    async (error) => {
      // Only process 401 errors (unauthorized)
      if (error.response?.status === 401 && !error.config.url.includes('/auth/')) {
        // Store the original request to retry later
        const originalRequest = error.config;
        
        // First try to refresh the token
        const refreshSuccess = await refreshAccessToken();
        
        if (refreshSuccess) {
          // Retry the original request with the new token
          return axios(originalRequest);
        }
        
        // If refresh failed, try to authenticate with Telegram
        const authSuccess = await authenticateWithTelegram();
        
        if (authSuccess) {
          // Retry the original request with the new token
          return axios(originalRequest);
        }
      }
      
      return Promise.reject(error);
    }
  );
}; 