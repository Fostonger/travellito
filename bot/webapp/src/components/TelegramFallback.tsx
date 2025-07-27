import React from 'react';
import { isRunningInTelegram } from '../auth';

interface TelegramFallbackProps {
  children: React.ReactNode;
  botUsername?: string;
}

/**
 * Component that renders children only if running inside Telegram WebApp,
 * otherwise shows a fallback UI with instructions
 */
const TelegramFallback: React.FC<TelegramFallbackProps> = ({ 
  children, 
  botUsername = 'travellito_bot'
}) => {
  const [isTelegram, setIsTelegram] = React.useState<boolean | null>(null);
  
  // React.useEffect(() => {
  //   // Check if running in Telegram on the client side
  //   setIsTelegram(isRunningInTelegram());
  // }, []);
  
  // // Show nothing during initial check
  // if (isTelegram === null) {
  //   return null;
  // }
  
  // // If running in Telegram, render children
  // if (isTelegram) {
  return <>{children}</>;
  // }
  
  // // Fallback UI when not running in Telegram
  // return (
  //   <div className="flex flex-col items-center justify-center min-h-screen p-4 bg-gray-100 text-center">
  //     <div className="bg-white p-6 rounded-lg shadow-md max-w-md w-full">
  //       <h1 className="text-2xl font-bold text-gray-800 mb-4">
  //         This app must be opened from Telegram
  //       </h1>
        
  //       <p className="text-gray-600 mb-6">
  //         This web app is designed to work only inside the Telegram messenger.
  //         Please open it using one of the methods below:
  //       </p>
        
  //       <div className="space-y-4">
  //         <div className="border border-gray-200 rounded p-4">
  //           <h2 className="font-semibold text-gray-700 mb-2">Option 1: Open via Bot</h2>
  //           <p className="text-sm text-gray-500 mb-3">
  //             Open our bot in Telegram and tap the "Browse Tours" button
  //           </p>
  //           <a 
  //             href={`https://t.me/${botUsername}`}
  //             target="_blank"
  //             rel="noopener noreferrer"
  //             className="inline-block bg-blue-500 hover:bg-blue-600 text-white px-4 py-2 rounded transition-colors"
  //           >
  //             Open Bot in Telegram
  //           </a>
  //         </div>
          
  //         <div className="border border-gray-200 rounded p-4">
  //           <h2 className="font-semibold text-gray-700 mb-2">Option 2: Direct Link</h2>
  //           <p className="text-sm text-gray-500 mb-3">
  //             Click the link below to open the app directly in Telegram
  //           </p>
  //           <a 
  //             href={`https://t.me/${botUsername}?startapp=main`}
  //             target="_blank"
  //             rel="noopener noreferrer"
  //             className="inline-block bg-blue-500 hover:bg-blue-600 text-white px-4 py-2 rounded transition-colors"
  //           >
  //             Open WebApp in Telegram
  //           </a>
  //         </div>
  //       </div>
  //     </div>
  //   </div>
  // );
};

export default TelegramFallback; 