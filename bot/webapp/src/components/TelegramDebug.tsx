import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { getApiBaseUrl, getInitDataSafely } from '../auth';

/**
 * Debug component for Telegram WebApp authentication issues
 * This should only be used during development
 */
const TelegramDebug: React.FC = () => {
  const [initData, setInitData] = useState<string>('');
  const [debugResult, setDebugResult] = useState<any>(null);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  
  // Get initData on mount
  useEffect(() => {
    const result = getInitDataSafely();
    if (result.ok && result.initData) {
      setInitData(result.initData);
    } else {
      setError(`Failed to get initData: ${result.reason}`);
    }
    
    // Log Telegram WebApp object
    if (window.Telegram?.WebApp) {
      console.log('Telegram WebApp object:', window.Telegram.WebApp);
    } else {
      console.error('Telegram WebApp object not found');
    }
  }, []);
  
  // Send initData to debug endpoint
  const analyzeInitData = async () => {
    setIsLoading(true);
    setError(null);
    
    try {
      const apiBase = getApiBaseUrl();
      const response = await axios.post(
        `${apiBase}/auth/telegram/debug`,
        { init_data: initData },
        { timeout: 5000 }
      );
      
      setDebugResult(response.data);
    } catch (err: any) {
      setError(`Error: ${err.message}`);
      console.error('Debug API error:', err);
    } finally {
      setIsLoading(false);
    }
  };
  
  return (
    <div className="p-4 bg-gray-100 rounded-lg">
      <h2 className="text-xl font-bold mb-4">Telegram WebApp Debug</h2>
      
      {error && (
        <div className="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded mb-4">
          {error}
        </div>
      )}
      
      <div className="mb-4">
        <label className="block text-gray-700 mb-2">initData:</label>
        <textarea
          className="w-full h-24 border rounded p-2 font-mono text-xs"
          value={initData}
          onChange={(e) => setInitData(e.target.value)}
        />
      </div>
      
      <button
        className="bg-blue-500 hover:bg-blue-700 text-white font-bold py-2 px-4 rounded"
        onClick={analyzeInitData}
        disabled={isLoading}
      >
        {isLoading ? 'Analyzing...' : 'Analyze initData'}
      </button>
      
      {debugResult && (
        <div className="mt-4">
          <h3 className="text-lg font-semibold mb-2">Analysis Results:</h3>
          
          <div className="bg-white p-4 rounded shadow overflow-auto">
            <div className="grid grid-cols-2 gap-2">
              <div className="font-semibold">Hash Valid:</div>
              <div className={debugResult.hash_valid ? 'text-green-600' : 'text-red-600'}>
                {debugResult.hash_valid ? 'Yes ✅' : 'No ❌'}
              </div>
              
              <div className="font-semibold">Auth Date Valid:</div>
              <div className={debugResult.auth_date_valid ? 'text-green-600' : 'text-red-600'}>
                {debugResult.auth_date_valid ? 'Yes ✅' : 'No ❌'}
              </div>
              
              <div className="font-semibold">Bot Token Configured:</div>
              <div className={debugResult.bot_token_configured ? 'text-green-600' : 'text-red-600'}>
                {debugResult.bot_token_configured ? 'Yes ✅' : 'No ❌'}
                {debugResult.bot_token_prefix && ` (${debugResult.bot_token_prefix})`}
              </div>
            </div>
            
            {debugResult.computed_hash && (
              <>
                <div className="mt-2 font-semibold">Computed Hash:</div>
                <div className="bg-gray-100 p-2 rounded font-mono text-xs break-all">
                  {debugResult.computed_hash}
                </div>
              </>
            )}
            
            {debugResult.received_hash && (
              <>
                <div className="mt-2 font-semibold">Received Hash:</div>
                <div className="bg-gray-100 p-2 rounded font-mono text-xs break-all">
                  {debugResult.received_hash}
                </div>
              </>
            )}
            
            {debugResult.user_data && (
              <>
                <div className="mt-2 font-semibold">User Data:</div>
                <pre className="bg-gray-100 p-2 rounded text-xs overflow-auto">
                  {JSON.stringify(debugResult.user_data, null, 2)}
                </pre>
              </>
            )}
            
            {debugResult.parsed_data && (
              <>
                <div className="mt-2 font-semibold">Parsed Data:</div>
                <pre className="bg-gray-100 p-2 rounded text-xs overflow-auto">
                  {JSON.stringify(debugResult.parsed_data, null, 2)}
                </pre>
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

export default TelegramDebug; 