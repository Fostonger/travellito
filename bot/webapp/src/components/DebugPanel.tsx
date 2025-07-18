import React, { useEffect, useState } from 'react';

// Debug panel that shows as a small icon in the corner, expandable to show logs
export const DebugPanel: React.FC = () => {
  const [isOpen, setIsOpen] = useState(false);
  const [logs, setLogs] = useState<string[]>([]);
  const [authInfo, setAuthInfo] = useState<{[key: string]: string}>({});

  // Check auth status on mount
  useEffect(() => {
    updateAuthInfo();
    
    // Create a global debug logger
    if (!window.debugLog) {
      window.debugLog = (message: string) => {
        setLogs(prev => [...prev, `${new Date().toLocaleTimeString()}: ${message}`]);
      };
    }
    
    // Log initial auth state
    window.debugLog('Debug panel initialized');
  }, []);
  
  const updateAuthInfo = () => {
    const info: {[key: string]: string} = {};
    
    // Check localStorage for tokens
    info['Access Token'] = localStorage.getItem('authToken') ? 'present' : 'missing';
    info['Refresh Token'] = localStorage.getItem('refreshToken') ? 'present' : 'missing';
    info['Token Expiry'] = localStorage.getItem('tokenExpiry') || 'unknown';
    info['Telegram User ID'] = localStorage.getItem('telegramUserId') || 'unknown';
    
    setAuthInfo(info);
  };
  
  const clearLogs = () => {
    setLogs([]);
  };
  
  const togglePanel = () => {
    setIsOpen(!isOpen);
    updateAuthInfo();
  };
  
  return (
    <div style={{
      position: 'fixed',
      bottom: '10px',
      right: '10px',
      zIndex: 1000
    }}>
      {/* Debug button */}
      <button 
        onClick={togglePanel}
        style={{
          width: '40px',
          height: '40px',
          borderRadius: '50%',
          backgroundColor: '#007AFF',
          color: 'white',
          border: 'none',
          fontSize: '20px',
          cursor: 'pointer',
          boxShadow: '0 2px 5px rgba(0,0,0,0.2)'
        }}
      >
        🐞
      </button>
      
      {/* Debug panel */}
      {isOpen && (
        <div style={{
          position: 'fixed',
          bottom: '60px',
          right: '10px',
          width: '300px',
          maxHeight: '400px',
          backgroundColor: '#333',
          color: '#fff',
          borderRadius: '8px',
          padding: '10px',
          boxShadow: '0 5px 15px rgba(0,0,0,0.3)',
          display: 'flex',
          flexDirection: 'column',
          overflow: 'hidden'
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '10px' }}>
            <h3 style={{ margin: 0 }}>Debug Info</h3>
            <button 
              onClick={clearLogs}
              style={{
                backgroundColor: '#555',
                color: 'white',
                border: 'none',
                padding: '2px 6px',
                borderRadius: '4px',
                cursor: 'pointer'
              }}
            >
              Clear
            </button>
          </div>
          
          {/* Auth info section */}
          <div style={{ marginBottom: '10px', padding: '8px', backgroundColor: '#444', borderRadius: '6px' }}>
            <h4 style={{ margin: '0 0 5px 0', color: '#00AAFF' }}>Auth Status:</h4>
            {Object.entries(authInfo).map(([key, value]) => (
              <div key={key} style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span>{key}:</span>
                <span style={{ color: value === 'missing' ? '#FF6B6B' : '#6BFF8A' }}>{value}</span>
              </div>
            ))}
            <button
              onClick={updateAuthInfo}
              style={{
                backgroundColor: '#555',
                color: 'white',
                border: 'none',
                padding: '2px 6px',
                borderRadius: '4px',
                marginTop: '5px',
                width: '100%',
                cursor: 'pointer'
              }}
            >
              Refresh
            </button>
          </div>
          
          {/* Logs section */}
          <div style={{ flex: 1, overflow: 'auto' }}>
            <h4 style={{ margin: '0 0 5px 0', color: '#00AAFF' }}>Logs:</h4>
            {logs.length === 0 ? (
              <div style={{ color: '#999', fontStyle: 'italic' }}>No logs yet</div>
            ) : (
              logs.map((log, idx) => (
                <div key={idx} style={{ 
                  borderBottom: '1px solid #555',
                  padding: '4px 0',
                  fontSize: '12px',
                  whiteSpace: 'pre-wrap',
                  wordBreak: 'break-word'
                }}>
                  {log}
                </div>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  );
};

// Add the global debug log function to the window object
declare global {
  interface Window {
    debugLog: (message: string) => void;
  }
}

export default DebugPanel; 