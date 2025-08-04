/**
 * auth.js - Token management and authentication utilities
 */

// Token storage keys
const ACCESS_TOKEN_KEY = 'auth_access_token';
const REFRESH_TOKEN_KEY = 'auth_refresh_token';
const TOKEN_EXP_KEY = 'auth_token_exp';

// Token refresh settings
const REFRESH_BEFORE_EXPIRY_MS = 6000; // Refresh 1 minute before expiry
const REFRESH_ENDPOINT = '/api/v1/auth/refresh';
const LOGOUT_ENDPOINT = '/api/v1/auth/logout';

// Helper to safely parse JSON
function safeJSONParse(str, defaultValue = null) {
  try {
    return str ? JSON.parse(str) : defaultValue;
  } catch (e) {
    console.error('Error parsing JSON:', e);
    return defaultValue;
  }
}

/**
 * Store authentication tokens
 * @param {Object} authData - Authentication data from server
 */
function storeTokens(authData) {
  if (!authData || !authData.access_token) return false;
  
  // Store access token
  localStorage.setItem(ACCESS_TOKEN_KEY, authData.access_token);
  
  // Store refresh token if available
  if (authData.refresh_token) {
    localStorage.setItem(REFRESH_TOKEN_KEY, authData.refresh_token);
  }
  
  // Calculate and store expiry time if possible
  try {
    // JWT tokens consist of three parts: header.payload.signature
    const payload = JSON.parse(atob(authData.access_token.split('.')[1]));
    if (payload.exp) {
      localStorage.setItem(TOKEN_EXP_KEY, payload.exp * 1000); // Convert to milliseconds
    }
  } catch (e) {
    console.error('Error parsing JWT token:', e);
  }
  
  return true;
}

/**
 * Get stored access token
 * @returns {string|null} The access token or null if not found
 */
function getAccessToken() {
  return localStorage.getItem(ACCESS_TOKEN_KEY);
}

/**
 * Get stored refresh token
 * @returns {string|null} The refresh token or null if not found
 */
function getRefreshToken() {
  return localStorage.getItem(REFRESH_TOKEN_KEY);
}

/**
 * Check if access token has expired
 * @returns {boolean} True if token has expired or expiry can't be determined
 */
function isTokenExpired() {
  const expiry = localStorage.getItem(TOKEN_EXP_KEY);
  if (!expiry) return true; // If we don't know when it expires, assume it's expired
  
  // Check if current time is past expiry time (with buffer)
  return Date.now() > (parseInt(expiry) - REFRESH_BEFORE_EXPIRY_MS);
}

/**
 * Check if authentication cookies are present
 * @returns {boolean} True if either access_token or refresh_token cookie is present
 */
function hasCookieAuth() {
  const cookies = document.cookie.split(';').map(c => c.trim());
  const hasAccessCookie = cookies.some(c => c.startsWith('access_token='));
  const hasRefreshCookie = cookies.some(c => c.startsWith('refresh_token='));
  
  return hasAccessCookie || hasRefreshCookie;
}

/**
 * Refresh the access token using the refresh token
 * @returns {Promise<boolean>} True if refresh was successful
 */
async function refreshAccessToken() {
  const refreshToken = getRefreshToken();
  
  // If no refresh token in localStorage, can't refresh
  if (!refreshToken) return false;
  
  try {
    const response = await fetch(REFRESH_ENDPOINT, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ refresh_token: refreshToken })
    });
    
    if (!response.ok) {
      // If refresh failed, clear tokens and return false
      clearTokens();
      return false;
    }
    
    const data = await response.json();
    
    // Store the new access token
    if (data.access_token) {
      localStorage.setItem(ACCESS_TOKEN_KEY, data.access_token);
      
      // Update the expiry time
      try {
        const payload = JSON.parse(atob(data.access_token.split('.')[1]));
        if (payload.exp) {
          localStorage.setItem(TOKEN_EXP_KEY, payload.exp * 1000);
        }
      } catch (e) {
        console.error('Error parsing refreshed JWT token:', e);
      }
      
      return true;
    }
    
    return false;
  } catch (error) {
    console.error('Error refreshing token:', error);
    return false;
  }
}

/**
 * Clear all stored tokens
 */
function clearTokens() {
  localStorage.removeItem(ACCESS_TOKEN_KEY);
  localStorage.removeItem(REFRESH_TOKEN_KEY);
  localStorage.removeItem(TOKEN_EXP_KEY);
}

/**
 * Logout the user by calling logout endpoint and clearing tokens
 * @returns {Promise<boolean>} True if logout was successful
 */
async function logout() {
  try {
    // Call the logout endpoint with token in header
    const accessToken = getAccessToken();
    await fetch(LOGOUT_ENDPOINT, {
      method: 'POST',
      headers: {
        'Authorization': accessToken ? `Bearer ${accessToken}` : ''
      }
    });
    
    // Clear tokens from localStorage
    clearTokens();
    
    // Redirect to login page
    window.location.href = '/login';
    return true;
  } catch (error) {
    console.error('Logout error:', error);
    // Still clear tokens even if the endpoint call fails
    clearTokens();
    window.location.href = '/login';
    return false;
  }
}

/**
 * Setup fetch interceptor to handle token refresh
 */
function setupFetchInterceptor() {
  // Store the original fetch function
  const originalFetch = window.fetch;
  
  // Replace with our interceptor
  window.fetch = async function(resource, options = {}) {
    // Clone the options
    const newOptions = { ...options };
    
    // Initialize headers if they don't exist
    newOptions.headers = newOptions.headers || {};
    
    // Always add Authorization header if we have a token
    const accessToken = getAccessToken();
    if (accessToken) {
      newOptions.headers = {
        ...newOptions.headers,
        'Authorization': `Bearer ${accessToken}`
      };
    }
    
    try {
      // Make the request
      const response = await originalFetch(resource, newOptions);
      
      // Handle 401 Unauthorized errors (token rejected)
      if (response.status === 401) {
        console.log('Got 401, trying to refresh token');
        
        // Try to refresh the token
        const refreshed = await refreshAccessToken();
        
        if (refreshed) {
          console.log('Token refreshed successfully, retrying request');
          // If refresh successful, retry the request with the new token
          const retryOptions = { ...newOptions };
          retryOptions.headers = {
            ...retryOptions.headers,
            'Authorization': `Bearer ${getAccessToken()}`
          };
          
          // Return the retried request
          return originalFetch(resource, retryOptions);
        } else {
          console.log('Token refresh failed, redirecting to login');
          // If refresh failed, redirect to login page
          if (window.location.pathname !== '/login') {
            window.location.href = '/login';
          }
        }
      }
      
      return response;
    } catch (error) {
      console.error('Fetch error:', error);
      throw error;
    }
  };
}

/**
 * Check if user is authenticated
 * @returns {boolean} True if user has valid tokens
 */
function isAuthenticated() {
  const hasAccessToken = !!getAccessToken();
  const hasRefreshToken = !!getRefreshToken();
  
  return hasAccessToken && hasRefreshToken;
}

// Initialize auth system
function initAuth() {
  setupFetchInterceptor();
  
  // Setup periodic check for token expiration
  setInterval(() => {
    if (isTokenExpired() && getRefreshToken()) {
      refreshAccessToken();
    }
  }, 60000); // Check every minute
}

// Export functions
window.AuthManager = {
  storeTokens,
  getAccessToken,
  getRefreshToken,
  isTokenExpired,
  hasCookieAuth,
  refreshAccessToken,
  clearTokens,
  logout,
  isAuthenticated,
  initAuth
};

// Initialize on load if document is already loaded
if (document.readyState === 'complete') {
  initAuth();
} else {
  // Otherwise wait for DOMContentLoaded
  document.addEventListener('DOMContentLoaded', initAuth);
} 