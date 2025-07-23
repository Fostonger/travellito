// Yandex Metrica integration
import axios, { AxiosInstance, AxiosStatic } from 'axios';

declare global {
  interface Window {
    ym: (counterId: number, action: string, ...args: any[]) => void;
    METRIKA_COUNTER: string;
  }
}

/**
 * Get Metrika counter ID from window variable
 * This is set in index.html and replaced with the environment variable during build
 */
const getMetrikaCounter = (): number => {
  return Number(window.METRIKA_COUNTER || "0");
};

/**
 * Get the Yandex Metrica client ID
 * @returns Promise that resolves to the client ID string
 */
export async function getClientId(): Promise<string> {
  const cached = localStorage.getItem("ym_client_id");
  if (cached) return cached;

  return new Promise<string>(resolve => {
    window.ym(getMetrikaCounter(), "getClientID", (id: string) => {
      localStorage.setItem("ym_client_id", id);
      resolve(id);
    });
  });
}

/**
 * Track an event with Yandex Metrica
 * @param name Event name
 * @param params Optional parameters
 */
export function trackEvent(name: string, params?: Record<string, any>): void {
  try {
    window.ym(getMetrikaCounter(), "reachGoal", name, params);
  } catch (error) {
    console.error("Error tracking event:", error);
  }
}

/**
 * Apply the client ID interceptor to an axios instance
 * @param axiosInstance The axios instance to apply the interceptor to
 */
export function applyClientIdInterceptor(axiosInstance: AxiosInstance | AxiosStatic = axios): void {
  // Add interceptor to include the Metrica client ID with every request
  axiosInstance.interceptors.request.use(async config => {
    try {
      // Get the Metrica client ID
      const clientId = await getClientId();
      if (clientId) {
        // Add it to request headers, but don't overwrite if it's already set
        if (!config.headers['X-Client-Id']) {
          config.headers['X-Client-Id'] = clientId;
        }
      }
    } catch (error) {
      // Silently fail - don't block API calls if analytics fails
      console.error('Failed to add client ID to request:', error);
    }
    return config;
  });
}

/**
 * Initialize the analytics system
 * Should be called once at app startup
 */
export function initAnalytics(): void {
  // Apply the client ID interceptor to the global axios instance
  applyClientIdInterceptor();
} 