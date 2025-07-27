/**
 * auth.js - Token management and authentication utilities
 */

// Token storage keys
const ACCESS_TOKEN_KEY = 'auth_access_token';
const REFRESH_TOKEN_KEY = 'auth_refresh_token';
const TOKEN_EXP_KEY = 'auth_token_exp';

// Token refresh settings
const REFRESH_BEFORE_EXPIRY_MS = 0; // Refresh 1 minute before expiry
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
 * @param {boolean} useCookies - If true, rely on cookies for refresh instead of sending token
 * @returns {Promise<boolean>} True if refresh was successful
 */
async function refreshAccessToken(useCookies = true) {
  // If we're using cookies and have them, don't send the token in the body
  const refreshToken = getRefreshToken();
  const hasCookies = hasCookieAuth();
  
  try {
    const options = {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      // Include credentials to send cookies
      credentials: 'include'
    };
    
    // Only send refresh token in body if we don't have cookies or explicitly asked not to use them
    if (!hasCookies || !useCookies) {
      if (!refreshToken) return false;
      options.body = JSON.stringify({ refresh_token: refreshToken });
    }
    
    const response = await fetch(REFRESH_ENDPOINT, options);
    
    if (!response.ok) {
      // If refresh failed, clear tokens and return false
      clearTokens();
      return false;
    }
    
    const data = await response.json();
    
    // Store the new access token
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
    // Call the logout endpoint to clear the session cookie
    await fetch(LOGOUT_ENDPOINT, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${getAccessToken()}`
      },
      credentials: 'include' // Include credentials to send cookies
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
    // Default options to include credentials
    options.credentials = options.credentials || 'include';
    
    // Try request with current token first (don't pre-refresh)
    // This is more efficient and lets the server middleware handle refresh if needed
    
    // Clone the options
    const newOptions = { ...options };
    
    // Initialize headers if they don't exist
    newOptions.headers = newOptions.headers || {};
    
    // Add Authorization header if we have a token and it's not already set
    // and not explicitly set to empty string (for cookie-only auth testing)
    const accessToken = getAccessToken();
    if (accessToken && !newOptions.headers.Authorization && newOptions.headers.Authorization !== '') {
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
        const refreshed = await refreshAccessToken(hasCookieAuth());
        
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
        } else if (!hasCookieAuth()) {
          console.log('Token refresh failed and no cookie auth, redirecting to login');
          // If refresh failed and we don't have cookie auth, redirect to login page
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
 * @returns {boolean} True if user has valid tokens or auth cookies
 */
function isAuthenticated() {
  const hasAccessToken = !!getAccessToken();
  const hasRefreshToken = !!getRefreshToken();
  const hasCookies = hasCookieAuth();
  
  return (hasAccessToken && hasRefreshToken) || hasCookies;
}

// Initialize auth system
function initAuth() {
  setupFetchInterceptor();
  
  // Setup periodic check for token expiration
  setInterval(() => {
    if (isTokenExpired() && (getRefreshToken() || hasCookieAuth())) {
      refreshAccessToken(hasCookieAuth());
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