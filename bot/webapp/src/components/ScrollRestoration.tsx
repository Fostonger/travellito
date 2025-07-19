import { useEffect, useRef } from 'react';
import { useLocation } from 'react-router-dom';

// Page scroll positions stored by path
const scrollPositions = new Map<string, number>();

/**
 * Component that handles scroll restoration when navigating between pages
 * Saves scroll position when leaving a page and restores it when coming back
 */
export default function ScrollRestoration() {
  const { pathname } = useLocation();
  const initialized = useRef(false);

  // Save scroll position when unmounting/changing route
  useEffect(() => {
    if (!initialized.current) {
      initialized.current = true;
      
      // Try to restore scroll position on initial mount
      const savedPosition = scrollPositions.get(pathname);
      if (savedPosition) {
        setTimeout(() => {
          window.scrollTo(0, savedPosition);
        }, 0);
      }
      
      return;
    }

    // When route changes, save the previous scroll position
    return () => {
      scrollPositions.set(pathname, window.scrollY);
    };
  }, [pathname]);

  return null;
} 