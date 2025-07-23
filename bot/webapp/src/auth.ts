// auth.ts - Authentication utilities for the webapp

import axios from 'axios';
import { getClientId } from './utils/analytics';

// Token storage keys and settings
const ACCESS_TOKEN_KEY = 'authToken'; // Keeping original key for backward compatibility
const REFRESH_TOKEN_KEY = 'refreshToken';
const TOKEN_EXP_KEY = 'tokenExpiry';
const TELEGRAM_USER_ID_KEY = 'telegramUserId';  // Store the real Telegram user ID

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
        showAlert: (message: string) => void;
      };
    };
  }
}

// Silent logger - does nothing in production
const log = (...args: any[]) => {
  // No logging in production
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
 * Get the stored Telegram user ID
 */
const getTelegramUserId = (): number | null => {
  const userId = localStorage.getItem(TELEGRAM_USER_ID_KEY);
  return userId ? Number(userId) : null;
};

/**
 * Store token information in localStorage
 */
const storeTokenInfo = (token: string) => {
  if (!token) return;
  
  try {
    // Store the access token
    localStorage.setItem(ACCESS_TOKEN_KEY, token);
    
    // Parse token to get expiration
    const payload = parseJwt(token);
    if (payload && payload.exp) {
      const expiryMs = payload.exp * 1000;
      localStorage.setItem(TOKEN_EXP_KEY, expiryMs.toString());
    }
  } catch (err) {
    // Silent fail
  }
};

/**
 * Store refresh token in localStorage with verification
 */
const storeRefreshToken = (token: string): boolean => {
  if (!token) return false;
  
  try {
    // Store the refresh token
    localStorage.setItem(REFRESH_TOKEN_KEY, token);
    
    // Verify it was stored correctly
    const storedToken = localStorage.getItem(REFRESH_TOKEN_KEY);
    return storedToken === token;
  } catch (err) {
    return false;
  }
};

/**
 * Preserve important headers like X-Client-Id when updating auth headers
 * @param headers The headers object to update with auth token
 * @param token The auth token to set
 */
const updateAuthHeadersPreservingClientId = async (headers: any, token: string) => {
  // Get client ID
  let clientId = headers['X-Client-Id'];
  
  // If clientId isn't already set in headers, try to get it
  if (!clientId) {
    try {
      clientId = await getClientId();
    } catch (error) {
      // Silent fail
    }
  }
  
  // Set authorization header
  headers['Authorization'] = `Bearer ${token}`;
  
  // Preserve client ID if available
  if (clientId) {
    headers['X-Client-Id'] = clientId;
  }
};

/**
 * Get a refresh token for the current access token
 * This function directly calls the backend to obtain a refresh token
 * for the current access token
 */
export const getRefreshToken = async (): Promise<boolean> => {
  try {
    // Get the Telegram user ID - this is critical to prevent duplicate users
    const telegramUserId = getTelegramUserId();
    if (!telegramUserId) {
      return false;
    }
    
    // Directly call the bot auth endpoint which returns both tokens
    const apiBase = getApiBaseUrl();
    
    // Use the TELEGRAM user ID (not the internal system ID)
    const response = await axios.post(`${apiBase}/auth/telegram/bot`, {
      id: telegramUserId,
      first_name: 'User',  // This will be overwritten by the backend with the correct value
      auth_date: Math.floor(Date.now() / 1000)
    });
    
    // The backend returns access_token and refresh_token directly in the response
    if (response.data) {
      if (response.data.refresh_token) {
        const stored = storeRefreshToken(response.data.refresh_token);
        
        // Also store access token if available
        if (response.data.access_token) {
          storeTokenInfo(response.data.access_token);
        }
        
        return stored;
      }
    }
    
    return false;
  } catch (error) {
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
  
  if (!refreshToken) {
    const gotToken = await getRefreshToken();
    if (!gotToken) {
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
    
    if (response.data && response.data.access_token) {
      storeTokenInfo(response.data.access_token);
      
      // Update axios headers
      axios.defaults.headers.common['Authorization'] = `Bearer ${response.data.access_token}`;
      
      return true;
    }
    
    return false;
  } catch (error) {
    // If we get a 401, clear the refresh token as it's invalid
    if (axios.isAxiosError(error) && error.response?.status === 401) {
      localStorage.removeItem(REFRESH_TOKEN_KEY);
    }
    
    return false;
  }
};

// Configure axios to include auth token in all requests
export const setupAxiosAuth = () => {
  // First check URL parameters for token (highest priority)
  const urlParams = new URLSearchParams(window.location.search);
  const tokenFromUrl = urlParams.get('token');
  const telegramUserId = urlParams.get('telegramUserId');
  
  // Store Telegram user ID if provided in URL
  if (telegramUserId) {
    localStorage.setItem(TELEGRAM_USER_ID_KEY, telegramUserId);
  }
  
  // Then check localStorage
  const tokenFromStorage = localStorage.getItem(ACCESS_TOKEN_KEY);
  
  // Use URL token if available, otherwise use stored token
  const authToken = tokenFromUrl || tokenFromStorage;
  
  if (tokenFromUrl) {
    // If token was in URL, save it to localStorage for future use
    storeTokenInfo(tokenFromUrl);
    
    // Also check for refresh token in URL
    const refreshTokenFromUrl = urlParams.get('refresh_token');
    if (refreshTokenFromUrl) {
      storeRefreshToken(refreshTokenFromUrl);
    }
    
    // Clean URL by removing the token parameters (for security)
    if (window.history && window.history.replaceState) {
      urlParams.delete('token');
      urlParams.delete('refresh_token');
      urlParams.delete('telegramUserId');
      const newUrl = window.location.pathname + 
        (urlParams.toString() ? '?' + urlParams.toString() : '') + 
        window.location.hash;
      window.history.replaceState({}, document.title, newUrl);
    }
  }
  
  // Get Telegram ID from WebApp if available
  if (window.Telegram?.WebApp?.initDataUnsafe?.user?.id) {
    const telegramId = window.Telegram.WebApp.initDataUnsafe.user.id;
    localStorage.setItem(TELEGRAM_USER_ID_KEY, telegramId.toString());
  }
  
  // Set authorization header if token available
  if (authToken) {
    axios.defaults.headers.common['Authorization'] = `Bearer ${authToken}`;
  }
  
  // Add response interceptor to handle 401 errors
  axios.interceptors.response.use(
    (response) => response,
    async (error) => {
      // Only process 401 errors (unauthorized)
      if (error.response?.status === 401 && !error.config.url.includes('/auth/refresh')) {
        // Try to refresh the token
        const refreshed = await refreshAccessToken();
        if (refreshed && error.config) {
          // Retry the original request with new token
          const newToken = localStorage.getItem(ACCESS_TOKEN_KEY);
          // Update headers preserving client ID
          if (newToken) {
            await updateAuthHeadersPreservingClientId(error.config.headers, newToken);
          }
          return axios(error.config);
        }
        
        // If refresh failed, try to authenticate with Telegram
        const success = await authenticateWithTelegram();
        
        if (success && error.config) {
          // Retry the original request with new token
          const newToken = localStorage.getItem(ACCESS_TOKEN_KEY);
          // Update headers preserving client ID
          if (newToken) {
            await updateAuthHeadersPreservingClientId(error.config.headers, newToken);
          }
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
        const refreshed = await refreshAccessToken();
        if (refreshed) {
          // Update the Authorization header
          const newToken = localStorage.getItem(ACCESS_TOKEN_KEY);
          if (newToken) {
            // Update headers preserving client ID
            await updateAuthHeadersPreservingClientId(config.headers, newToken);
          }
        }
      }
      
      return config;
    },
    (error) => Promise.reject(error)
  );
  
  // Check if we have a token but no refresh token - get one if needed
  setTimeout(async () => {
    const accessToken = localStorage.getItem(ACCESS_TOKEN_KEY);
    const refreshToken = localStorage.getItem(REFRESH_TOKEN_KEY);
    
    if (accessToken && !refreshToken) {
      await getRefreshToken();
    }
  }, 1000); // Delay slightly to ensure other initializations complete
};

// Authenticate with the backend using Telegram WebApp data
export const authenticateWithTelegram = async () => {
  try {
    // Check if we have Telegram WebApp data
    if (window.Telegram?.WebApp?.initDataUnsafe?.user) {
      const user = window.Telegram.WebApp.initDataUnsafe.user;
      
      // Store the Telegram user ID for future use
      localStorage.setItem(TELEGRAM_USER_ID_KEY, user.id.toString());
      
      // Prepare user data for authentication
      const userData = {
        id: user.id,  // This is the critical field - using actual Telegram ID
        first_name: user.first_name || 'User',
        last_name: user.last_name,
        username: user.username,
        auth_date: Math.floor(Date.now() / 1000),  // Using standard Unix timestamp
        hash: window.Telegram.WebApp.initData || '',
      };
      
      const apiBase = getApiBaseUrl();
      
      try {
        // Call auth endpoint with a longer timeout to ensure it completes
        const response = await axios.post(`${apiBase}/auth/telegram/bot`, userData, {
          timeout: 10000 // 10 second timeout
        });
        
        // Process auth response
        if (response.data && typeof response.data === 'object') {
          // Store access token if available
          if (response.data.access_token) {
            storeTokenInfo(response.data.access_token);
            
            // Set authorization header for future requests
            axios.defaults.headers.common['Authorization'] = `Bearer ${response.data.access_token}`;
          }
          
          // Store refresh token if available
          if (response.data.refresh_token) {
            storeRefreshToken(response.data.refresh_token);
          }
          
          // Return success if we got at least an access token
          if (response.data.access_token) {
            return true;
          }
        }
        
        return false;
      } catch (apiError) {
        return false;
      }
    } else {
      // Try to use stored Telegram user ID as fallback
      const telegramUserId = getTelegramUserId();
      if (telegramUserId) {
        try {
          const apiBase = getApiBaseUrl();
          const response = await axios.post(`${apiBase}/auth/telegram/bot`, {
            id: telegramUserId,
            first_name: 'User',
            auth_date: Math.floor(Date.now() / 1000)
          }, {
            timeout: 10000
          });
          
          if (response.data?.access_token) {
            storeTokenInfo(response.data.access_token);
            
            if (response.data.refresh_token) {
              storeRefreshToken(response.data.refresh_token);
            }
            
            axios.defaults.headers.common['Authorization'] = `Bearer ${response.data.access_token}`;
            return true;
          }
        } catch (idError) {
          // Silent fail
        }
      }
      
      return false;
    }
  } catch (error) {
    return false;
  }
}; 