import { useEffect } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';

// We only need to store the scroll position for the main tours list
// This simplifies the logic and ensures we don't have conflicting positions
let toursListScrollPosition = 0;

/**
 * Simple component to store and restore scroll position ONLY for the main tours list
 */
export default function ScrollRestoration() {
  const location = useLocation();
  const navigate = useNavigate();
  
  // Only handle scroll restoration for specific route transitions
  useEffect(() => {
    // Main tours list route
    if (location.pathname === '/') {
      console.log('Tours list page: Restoring scroll to', toursListScrollPosition);
      
      // Restore scroll position with a small delay to ensure content is rendered
      const timerId = setTimeout(() => {
        window.scrollTo({
          top: toursListScrollPosition,
          behavior: 'instant' // Use instant to avoid animation
        });
      }, 50);
      
      return () => {
        // When leaving the tours list, save the current scroll position
        toursListScrollPosition = window.scrollY;
        console.log('Leaving tours list: Saved scroll position', toursListScrollPosition);
        clearTimeout(timerId);
      };
    } 
    else if (location.pathname.startsWith('/tour/')) {
      // When viewing a tour, we want to start at the top
      window.scrollTo(0, 0);
      
      // No cleanup needed for tour detail pages
      return;
    }
    else if (location.pathname === '/bookings') {
      // When viewing bookings, we want to start at the top
      window.scrollTo(0, 0);
      
      // No cleanup needed for bookings page
      return;
    }
    
  }, [location.pathname]);
  
  // Reset scroll position when explicitly clicking the "Tours" link
  // or going back to home from another page
  useEffect(() => {
    // Create cleanup function to handle the case when component unmounts
    return () => {
      // Don't reset scroll when navigating between tours and tour details
      const isNavigatingToTourDetail = location.pathname.startsWith('/tour/');
      if (!isNavigatingToTourDetail && location.pathname !== '/') {
        toursListScrollPosition = 0;
      }
    };
  }, []);
  
  return null;
} 