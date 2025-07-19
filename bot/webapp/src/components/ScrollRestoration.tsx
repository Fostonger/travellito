import { useEffect, useRef } from 'react';
import { useLocation } from 'react-router-dom';

// Page scroll positions stored by path
const scrollPositions = new Map<string, number>();

/**
 * Component that handles scroll restoration when navigating between pages
 */
export default function ScrollRestoration() {
  const { pathname } = useLocation();
  const prevPathRef = useRef<string | null>(null);
  
  // On mount, disable browser's scroll restoration
  useEffect(() => {
    if (window.history && 'scrollRestoration' in window.history) {
      // Disable browser's automatic scroll restoration
      window.history.scrollRestoration = 'manual';
    }
    
    return () => {
      // Restore browser's default behavior on unmount
      if (window.history && 'scrollRestoration' in window.history) {
        window.history.scrollRestoration = 'auto';
      }
    };
  }, []);
  
  // Handle scroll position on pathname change
  useEffect(() => {
    // On first mount or component initialization
    if (!prevPathRef.current) {
      prevPathRef.current = pathname;
      return;
    }
    
    // When navigating to a new page:
    // 1. Save scroll position of the current page before leaving
    const currentPosition = window.scrollY;
    if (currentPosition > 0) {
      scrollPositions.set(prevPathRef.current, currentPosition);
    }
    
    // 2. Update prevPath for next navigation
    prevPathRef.current = pathname;
    
    // 3. Restore scroll position if coming back to a page, or scroll to top
    window.requestAnimationFrame(() => {
      // Give the page some time to render content before scrolling
      setTimeout(() => {
        const savedPosition = scrollPositions.get(pathname);
        if (savedPosition) {
          window.scrollTo(0, savedPosition);
        } else {
          window.scrollTo(0, 0);
        }
      }, 100);
    });
  }, [pathname]);
  
  // Clean up on unmount - save final scroll position
  useEffect(() => {
    return () => {
      if (prevPathRef.current) {
        const finalPosition = window.scrollY;
        if (finalPosition > 0) {
          scrollPositions.set(prevPathRef.current, finalPosition);
        }
      }
    };
  }, []);
  
  return null;
} 