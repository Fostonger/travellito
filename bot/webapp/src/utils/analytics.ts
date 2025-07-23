// Yandex Metrica integration
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
 * Initialize the analytics system
 * Should be called once at app startup
 */
export function initAnalytics(): void {
  // The actual Metrica code is injected in index.html
  // This function is used for any additional initialization
} 