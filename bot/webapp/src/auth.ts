// auth.ts - Authentication utilities for the webapp

import axios from 'axios';

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

// Configure axios to include auth token in all requests
export const setupAxiosAuth = () => {
  // First check URL parameters for token (highest priority)
  const urlParams = new URLSearchParams(window.location.search);
  const tokenFromUrl = urlParams.get('token');
  
  // Then check localStorage
  const tokenFromStorage = localStorage.getItem('authToken');
  
  // Use URL token if available, otherwise use stored token
  const authToken = tokenFromUrl || tokenFromStorage;
  
  if (tokenFromUrl) {
    // If token was in URL, save it to localStorage for future use
    localStorage.setItem('authToken', tokenFromUrl);
    console.log('Auth token saved from URL parameters');
    
    // Clean URL by removing the token parameter (for security)
    if (window.history && window.history.replaceState) {
      urlParams.delete('token');
      const newUrl = window.location.pathname + 
        (urlParams.toString() ? '?' + urlParams.toString() : '') + 
        window.location.hash;
      window.history.replaceState({}, document.title, newUrl);
    }
  } else {
    console.log('No auth token in URL parameters, using stored token:', !!tokenFromStorage);
  }
  
  if (authToken) {
    axios.defaults.headers.common['Authorization'] = `Bearer ${authToken}`;
    console.log('Auth token set in axios defaults');
  } else {
    console.warn('No auth token available');
  }
  
  // Add response interceptor to handle 401 errors
  axios.interceptors.response.use(
    (response) => response,
    async (error) => {
      console.log('Axios error:', error.response?.status, error.config?.url);
      
      if (error.response && error.response.status === 401) {
        console.warn('401 Unauthorized error detected');
        
        // Clear invalid token
        localStorage.removeItem('authToken');
        console.log('Auth token removed from localStorage');
        
        // Try to authenticate with Telegram
        const success = await authenticateWithTelegram();
        console.log('Re-authentication attempt result:', success);
        
        if (success && error.config) {
          // Retry the original request with the new token
          console.log('Retrying original request');
          const authToken = localStorage.getItem('authToken');
          if (authToken) {
            error.config.headers['Authorization'] = `Bearer ${authToken}`;
            return axios(error.config);
          }
        }
      } else if (error.response && error.response.status === 422) {
        console.error('Validation error:', error.response.data);
      }
      
      return Promise.reject(error);
    }
  );
};

// Authenticate with the backend using Telegram WebApp data
export const authenticateWithTelegram = async () => {
  // @ts-ignore - Vite specific environment variable
  const apiBase = import.meta.env?.VITE_API_BASE || 'http://localhost:8000/api/v1';
  
  console.log('Attempting to authenticate with Telegram WebApp data');
  
  try {
    // Check if we have Telegram WebApp data
    if (window.Telegram?.WebApp?.initDataUnsafe?.user) {
      const user = window.Telegram.WebApp.initDataUnsafe.user;
      console.log('Found Telegram user data:', user.id, user.first_name);
      
      // Add hash from initData for verification
      const userData = {
        id: user.id,
        first_name: user.first_name,
        last_name: user.last_name,
        username: user.username,
        auth_date: Date.now(),
        hash: window.Telegram.WebApp.initData,
      };
      
      console.log('Calling auth endpoint with user data');
      
      // Call auth endpoint
      const response = await axios.post(`${apiBase}/auth/telegram/webapp`, userData);
      
      console.log('Auth response:', response.status, response.data?.ok);
      
      if (response.data && response.data.access_token) {
        // Store token
        localStorage.setItem('authToken', response.data.access_token);
        console.log('Token stored in localStorage');
        
        // Set for future requests
        axios.defaults.headers.common['Authorization'] = `Bearer ${response.data.access_token}`;
        console.log('Token set in axios defaults');
        
        return true;
      } else {
        console.warn('No access token in response');
      }
    } else {
      console.warn('No Telegram WebApp user data available');
    }
    return false;
  } catch (error) {
    console.error('Authentication error:', error);
    return false;
  }
}; 