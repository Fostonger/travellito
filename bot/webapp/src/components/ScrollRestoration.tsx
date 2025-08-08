import { useEffect } from 'react';
import { useLocation } from 'react-router-dom';

// We only need to store the scroll position for the main tours list
// This simplifies the logic and ensures we don't have conflicting positions
let toursListScrollPosition = 0;

/**
 * Attempt to restore scroll position after the view is rendered.
 * We retry until either:
 *  - The content height is tall enough to reach the saved position, OR
 *  - We hit a maximum number of attempts.
 */
function restoreScroll(pos: number) {
  const maxAttempts = 20; // ~1s with 50 ms interval
  let attempts = 0;

  const tryRestore = () => {
    // Only restore if the content is tall enough
    const pageHeight = document.documentElement.scrollHeight;
    const viewportHeight = window.innerHeight;

    if (pageHeight >= pos + viewportHeight) {
      window.scrollTo({ top: pos, behavior: 'auto' });
      return;
    }

    if (attempts < maxAttempts) {
      attempts += 1;
      setTimeout(tryRestore, 50);
    } else {
      // Fallback – just scroll to bottom if we still can't reach the saved pos
      window.scrollTo({ top: pageHeight, behavior: 'auto' });
    }
  };

  tryRestore();
}

/**
 * Simple component to store and restore scroll position ONLY for the main tours list
 */
export default function ScrollRestoration() {
  const location = useLocation();

  // Track scroll position live while on the tours list so we always have the latest
  useEffect(() => {
    if (!location.pathname.startsWith('/tours')) return;

    const onScroll = () => {
      toursListScrollPosition = window.scrollY;
    };

    window.addEventListener('scroll', onScroll, { passive: true });

    return () => {
      window.removeEventListener('scroll', onScroll);
    };
  }, [location.pathname]);

  // Handle restoration when entering a route
  useEffect(() => {
    // 1. Tours list route
    if (location.pathname.startsWith('/tours')) {
      console.log('[ScrollRestoration] Attempting to restore scroll', toursListScrollPosition);
      restoreScroll(toursListScrollPosition);
      return;
    }

    // 2. Other routes should start at top immediately
    if (location.pathname.startsWith('/tour/') || location.pathname === '/bookings') {
      window.scrollTo({ top: 0, left: 0, behavior: 'auto' });
    }
  }, [location.pathname]);

  // Reset scroll position when explicitly clicking the "Tours" link
  // or going back to home from another page
  useEffect(() => {
    // Create cleanup function to handle the case when component unmounts
    return () => {
      // Don't reset scroll when navigating between tours and tour details
      const isNavigatingToTourDetail = location.pathname.startsWith('/tour/');
      if (!isNavigatingToTourDetail && !location.pathname.startsWith('/tours')) {
        toursListScrollPosition = 0;
      }
    };
  }, []);

  return null;
} 
