import React, { useEffect, useState } from 'react';
import { refreshAccessToken } from '../auth';

const TokenRefreshTest: React.FC = () => {
  const [accessToken, setAccessToken] = useState<string | null>(null);
  const [refreshToken, setRefreshToken] = useState<string | null>(null);
  const [tokenExpiry, setTokenExpiry] = useState<string | null>(null);
  const [isExpired, setIsExpired] = useState<boolean | null>(null);
  const [apiResponse, setApiResponse] = useState<string>('No API call made yet');

  // Parse JWT token and extract expiration
  const parseToken = (token: string | null): any => {
    if (!token) return null;
    try {
      const base64Url = token.split('.')[1];
      const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');
      const jsonPayload = decodeURIComponent(atob(base64).split('').map(c => {
        return '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2);
      }).join(''));
      return JSON.parse(jsonPayload);
    } catch (error) {
      console.error('Error parsing token:', error);
      return null;
    }
  };

  // Truncate token for display
  const truncateToken = (token: string | null): string => {
    if (!token) return 'None';
    if (token.length <= 20) return token;
    return token.substring(0, 10) + '...' + token.substring(token.length - 10);
  };

  // Update token status
  const updateTokenStatus = () => {
    const storedAccessToken = localStorage.getItem('authToken');
    const storedRefreshToken = localStorage.getItem('refreshToken');
    const storedExpiry = localStorage.getItem('tokenExpiry');
    
    setAccessToken(storedAccessToken);
    setRefreshToken(storedRefreshToken);
    
    if (storedExpiry) {
      const expiryDate = new Date(parseInt(storedExpiry));
      setTokenExpiry(expiryDate.toLocaleString());
      setIsExpired(Date.now() > parseInt(storedExpiry));
    } else if (storedAccessToken) {
      // Try to extract expiry from token
      const payload = parseToken(storedAccessToken);
      if (payload?.exp) {
        const expiryMs = payload.exp * 1000;
        const expiryDate = new Date(expiryMs);
        setTokenExpiry(expiryDate.toLocaleString());
        setIsExpired(Date.now() > expiryMs);
      } else {
        setTokenExpiry('Unknown');
        setIsExpired(null);
      }
    } else {
      setTokenExpiry('None');
      setIsExpired(null);
    }
  };

  // Force token refresh
  const handleRefreshToken = async () => {
    setApiResponse('Refreshing token...');
    const success = await refreshAccessToken();
    setApiResponse(success ? 'Token refreshed successfully!' : 'Token refresh failed');
    updateTokenStatus();
  };

  // Make test API call
  const handleApiCall = async () => {
    setApiResponse('Making API call...');
    try {
      // @ts-ignore - Vite specific environment variable
      const apiBase = import.meta.env?.VITE_API_BASE || 'http://localhost:8000/api/v1';
      const response = await fetch(`${apiBase}/auth/me`, {
        headers: {
          'Authorization': `Bearer ${accessToken}`
        }
      });
      
      const data = await response.json();
      setApiResponse(JSON.stringify(data, null, 2));
    } catch (error) {
      setApiResponse(`API call error: ${error instanceof Error ? error.message : String(error)}`);
    }
    updateTokenStatus();
  };

  // Clear all tokens
  const handleClearTokens = () => {
    localStorage.removeItem('authToken');
    localStorage.removeItem('refreshToken');
    localStorage.removeItem('tokenExpiry');
    setApiResponse('All tokens cleared');
    updateTokenStatus();
  };

  // Update status on mount and every 5 seconds
  useEffect(() => {
    updateTokenStatus();
    const interval = setInterval(updateTokenStatus, 5000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="p-4 max-w-lg mx-auto">
      <h1 className="text-2xl font-bold mb-4">Token Refresh Test</h1>
      
      {/* Token Status */}
      <div className="bg-white shadow rounded-lg p-4 mb-4">
        <h2 className="font-bold mb-2">Token Status</h2>
        <div className="space-y-2 text-sm">
          <p><span className="font-medium">Access Token:</span> {truncateToken(accessToken)}</p>
          <p><span className="font-medium">Refresh Token:</span> {truncateToken(refreshToken)}</p>
          <p><span className="font-medium">Token Expires:</span> {tokenExpiry}</p>
          <p><span className="font-medium">Is Expired:</span> 
            <span className={isExpired === true ? 'text-red-500' : 
                             isExpired === false ? 'text-green-500' : ''}>
              {isExpired === null ? 'Unknown' : isExpired ? ' Yes' : ' No'}
            </span>
          </p>
        </div>
      </div>
      
      {/* Actions */}
      <div className="bg-white shadow rounded-lg p-4 mb-4">
        <h2 className="font-bold mb-2">Actions</h2>
        <div className="flex flex-wrap gap-2">
          <button 
            onClick={handleRefreshToken}
            className="bg-blue-500 text-white px-3 py-1 rounded hover:bg-blue-600"
          >
            Refresh Token
          </button>
          <button 
            onClick={handleApiCall}
            className="bg-green-500 text-white px-3 py-1 rounded hover:bg-green-600"
          >
            Test API Call
          </button>
          <button 
            onClick={handleClearTokens}
            className="bg-red-500 text-white px-3 py-1 rounded hover:bg-red-600"
          >
            Clear Tokens
          </button>
        </div>
      </div>
      
      {/* API Response */}
      <div className="bg-white shadow rounded-lg p-4">
        <h2 className="font-bold mb-2">API Response</h2>
        <pre className="bg-gray-100 p-2 rounded text-xs overflow-auto whitespace-pre-wrap">
          {apiResponse}
        </pre>
      </div>
    </div>
  );
};

export default TokenRefreshTest; 