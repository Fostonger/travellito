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

    const apiBase = getApiBaseUrl();
    
    try {
      // Call the new secure auth endpoint with initData
      const response = await axios.post(
        `${apiBase}/auth/telegram/init`, 
        { init_data: initDataResult.initData },
        { 
          withCredentials: true, // Important: needed to receive and send cookies
          timeout: 10000 // 10 second timeout
        }
      );
      
      // Check if authentication was successful
      if (response.data && response.data.user) {
        return true;
      }
      
      return false;
    } catch (apiError) {
      console.error('Authentication API error:', apiError);
      return false;
    }
  } catch (error) {
    console.error('Telegram WebApp authentication error:', error);
    return false;
  }
};

/**
 * Check if the user is authenticated by making a test request
 */
export const checkAuthentication = async (): Promise<boolean> => {
  try {
    const apiBase = getApiBaseUrl();
    await axios.get(`${apiBase}/auth/me`, { withCredentials: true });
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
    await axios.post(`${apiBase}/auth/logout`, {}, { withCredentials: true });
    return true;
  } catch (error) {
    return false;
  }
};

/**
 * Configure axios to include auth cookies and handle 401 errors
 */
export const setupAxiosAuth = () => {
  // Configure axios to include credentials (cookies)
  axios.defaults.withCredentials = true;
  
  // Add client ID header to all requests
  axios.interceptors.request.use(async (config) => {
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
        // Try to authenticate with Telegram
        const success = await authenticateWithTelegram();
        
        if (success && error.config) {
          // Retry the original request
          return axios(error.config);
        }
      }
      
      return Promise.reject(error);
    }
  );
  
  // Try to authenticate immediately if running in Telegram
  if (isRunningInTelegram()) {
    setTimeout(async () => {
      await authenticateWithTelegram();
    }, 100);
  }
}; 