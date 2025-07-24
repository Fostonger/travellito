// @ts-nocheck
import React, { useEffect, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import axios from 'axios';
import { t, fmtPrice } from '../i18n';
import { formatTime, formatFullDate, getDepartureDate } from '../utils/dateUtils';
import { parsePhoneNumber, isValidPhoneNumber } from 'libphonenumber-js';

export default function Checkout() {
  const nav = useNavigate();
  const { state } = useLocation() as any;
  if (!state?.tourId || !state.departure) {
    return <p>{t('missing_ctx')}</p>;
  }
  const tourId = state.tourId;
  const departure = state.departure;
  const apiBase = import.meta.env.VITE_API_BASE || 'http://localhost:8000/api/v1';

  const [categories, setCategories] = useState([]);
  const [quantities, setQuantities] = useState<any>({});
  const [quote, setQuote] = useState<any>(null);
  // Load saved user info from localStorage if available
  const [contactInfo, setContactInfo] = useState(() => {
    const savedInfo = localStorage.getItem('userContactInfo');
    return savedInfo ? JSON.parse(savedInfo) : {
      name: '',
      phone: ''
    };
  });
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState('');
  const [phoneError, setPhoneError] = useState('');

  useEffect(() => {
    const load = async () => {
      const { data } = await axios.get(`${apiBase}/public/tours/${tourId}/categories`);
      setCategories(data);
    };
    load();
    
    // Debug information about the departure
    console.log('Departure data:', {
      id: departure.id,
      starts_at: departure.starts_at,
      is_virtual: departure.is_virtual,
      virtual_timestamp: departure.virtual_timestamp,
      tourId
    });
    
    // Log the parsed date and time for debugging
    const departureDate = getDepartureDate(departure);
    console.log('Parsed departure date:', departureDate.toString());
    console.log('Local time:', formatTime(departure.starts_at));
    console.log('UTC time:', departureDate.toUTCString());
  }, [tourId]);

  const validatePhoneNumber = (phone: string) => {
    try {
      if (!phone) {
        setPhoneError(t('phone_required'));
        return false;
      }
      
      if (!isValidPhoneNumber(phone)) {
        setPhoneError(t('invalid_phone'));
        return false;
      }
      
      const phoneNumber = parsePhoneNumber(phone);
      if (!phoneNumber.isValid()) {
        setPhoneError(t('invalid_phone'));
        return false;
      }
      
      setPhoneError('');
      return true;
    } catch (err) {
      console.error('Phone validation error:', err);
      setPhoneError(t('invalid_phone'));
      return false;
    }
  };

  const recalc = async (qs: any) => {
    const items = Object.entries(qs)
      .filter(([, qty]) => qty > 0)
      .map(([cid, qty]) => ({ category_id: Number(cid), qty }));
    if (!items.length) return setQuote(null);
    
    try {
      // Get auth token from localStorage
      const authToken = localStorage.getItem('authToken');
      if (!authToken) {
        console.error('No auth token found');
        setError(t('auth_required'));
        return;
      }
      
      // Make sure departure ID is a number
      const departureId = typeof departure.id === 'string' 
        ? parseInt(departure.id) 
        : departure.id;
      
      console.log('Sending quote request with departure_id:', departureId, 'Type:', typeof departureId);
      
      // Prepare the quote payload
      const quotePayload: any = {
        departure_id: departureId,
        items
      };
      
      // Log the timestamp format for debugging
      console.log('Using pure UTC timestamp format without timezone adjustment');
      
      // If this is a virtual departure, include the timestamp
      if (departure.is_virtual && departure.virtual_timestamp) {
        quotePayload.virtual_timestamp = departure.virtual_timestamp;
        console.log('Including virtual timestamp in quote:', departure.virtual_timestamp);
      }
      
      console.log('Quote payload:', JSON.stringify(quotePayload));
      
      const { data } = await axios.post(`${apiBase}/public/quote`, quotePayload, {
        headers: {
          'Authorization': `Bearer ${authToken}`
        }
      });
      
      console.log('Quote response:', data);
      
      // If the server materialized a virtual departure, update our local state
      if (departure.is_virtual && data.departure_id && data.departure_id !== departure.id) {
        console.log('Virtual departure was materialized with ID:', data.departure_id);
        // Save the original virtual timestamp before updating the ID
        const originalTimestamp = departure.virtual_timestamp;
        departure.id = data.departure_id;
        departure.is_virtual = false;
        // Keep the original timestamp for consistent display
        departure.virtual_timestamp = originalTimestamp;
      }
      
      setQuote(data);
    } catch (err) {
      console.error('Error getting quote:', err);
      if (err.response) {
        console.error('Error response:', err.response.status, err.response.data);
      }
      setError(t('quote_error'));
      
      // If unauthorized, try to redirect to authentication
      if (err.response?.status === 401) {
        setError(t('auth_required'));
      } else if (err.response?.status === 404 && departure.is_virtual) {
        // Special handling for virtual departures that couldn't be materialized
        setError(t('virtual_departure_error'));
      } else if (err.response?.status === 400) {
        setError(`${t('quote_error')}: ${err.response.data?.detail || 'Bad request'}`);
      }
    }
  };

  const handleQtyChange = (cid: number, qty: number) => {
    const next = { ...quantities, [cid]: qty };
    setQuantities(next);
    recalc(next);
  };

  const handleContactChange = (field: string, value: string) => {
    setContactInfo({
      ...contactInfo,
      [field]: value
    });
    
    // Validate phone when it changes
    if (field === 'phone') {
      validatePhoneNumber(value);
    }
  };

  const handleConfirm = async () => {
    // Validate contact info
    if (!contactInfo.name.trim()) {
      setError(t('name_required'));
      return;
    }
    
    // Validate phone number
    if (!validatePhoneNumber(contactInfo.phone)) {
      setError(phoneError || t('phone_required'));
      return;
    }
    
    // Validate at least one ticket selected
    const items = Object.entries(quantities)
      .filter(([, qty]) => qty > 0)
      .map(([cid, qty]) => ({ category_id: Number(cid), qty }));
    
    if (items.length === 0) {
      setError(t('select_tickets'));
      return;
    }
    
    // Save contact info to localStorage for future use
    localStorage.setItem('userContactInfo', JSON.stringify(contactInfo));
    
    setIsSubmitting(true);
    setError('');
    
    try {
      // Get auth token from localStorage
      const authToken = localStorage.getItem('authToken');
      if (!authToken) {
        console.error('No auth token found');
        setError(t('auth_required'));
        setIsSubmitting(false);
        return;
      }
      
      // Use the real departure ID (which might have been updated if this was a virtual departure)
      console.log('Booking with departure ID:', departure.id, 'Type:', typeof departure.id);
      
      // Make sure departure ID is a number
      const departureId = typeof departure.id === 'string' 
        ? parseInt(departure.id) 
        : departure.id;
        
      console.log('Final departure ID being sent:', departureId, 'Type:', typeof departureId);
      
      // Prepare the booking payload
      const bookingPayload: any = {
        departure_id: departureId,
        items,
        contact_name: contactInfo.name,
        contact_phone: contactInfo.phone
      };
      
      // Log the timestamp format for debugging
      console.log('Using pure UTC timestamp format without timezone adjustment');
      
      // If this was originally a virtual departure, include the timestamp
      // even if it has been materialized
      if (departure.virtual_timestamp) {
        bookingPayload.virtual_timestamp = departure.virtual_timestamp;
        console.log('Including virtual timestamp:', departure.virtual_timestamp);
      }
      
      console.log('Booking payload:', JSON.stringify(bookingPayload));
      
      await axios.post(`${apiBase}/public/bookings`, bookingPayload, {
        headers: {
          'Authorization': `Bearer ${authToken}`
        }
      });
      ym(103412565,'reachGoal','booking-create');
      alert(t('booking_confirmed'));
      nav('/bookings');
    } catch (err) {
      console.error('Booking error:', err);
      if (err.response) {
        console.error('Error response:', err.response.status, err.response.data);
      }
      
      // Handle specific error cases
      if (err.response?.status === 401) {
        setError(t('auth_required'));
      } else if (err.response?.status === 422) {
        setError(t('validation_error'));
      } else if (err.response?.status === 400) {
        setError(`${t('booking_error')}: ${err.response.data?.detail || 'Bad request'}`);
      } else {
        setError(t('booking_error'));
      }
      
      setIsSubmitting(false);
    }
  };

  // Format dates using the utility function
  const departureDate = formatFullDate(departure.starts_at);
  const departureTime = formatTime(departure.starts_at);

  return (
    <div className="p-4 pb-20 bg-gray-50 min-h-screen">
      <div className="mb-4">
        <button onClick={() => nav(-1)} className="text-blue-600 font-medium flex items-center">
          <span className="mr-1">←</span> {t('back')}
        </button>
      </div>
      
      <div className="bg-white rounded-xl shadow-md overflow-hidden mb-4">
        <div className="p-4 bg-blue-600 text-white">
          <h2 className="text-xl font-bold">{t('checkout').replace('{date}', departureTime)}</h2>
          <p className="opacity-90">{departureDate}</p>
        </div>
        
        {/* Ticket selection */}
        <div className="p-4 border-b">
          <h3 className="font-semibold mb-3">{t('select_tickets')}</h3>
          
          <div className="space-y-4">
            {categories.map((c: any) => (
              <div key={c.id} className="flex items-center justify-between border-b pb-3">
                <div>
                  <div className="font-medium">{c.name}</div>
                  <div className="text-blue-600 font-semibold">{fmtPrice(c.price_net)}</div>
                </div>
                <div className="flex items-center">
                  <button 
                    className="w-8 h-8 rounded-full bg-gray-200 flex items-center justify-center"
                    onClick={() => handleQtyChange(c.id, Math.max(0, (quantities[c.id] || 0) - 1))}
                  >
                    -
                  </button>
                  <input
                    type="number"
                    min="0"
                    className="w-12 text-center mx-2 border rounded"
                    value={quantities[c.id] || ''}
                    onChange={(e) => handleQtyChange(c.id, Number(e.target.value))}
                  />
                  <button 
                    className="w-8 h-8 rounded-full bg-blue-600 text-white flex items-center justify-center"
                    onClick={() => handleQtyChange(c.id, (quantities[c.id] || 0) + 1)}
                  >
                    +
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
        
        {/* Contact information */}
        <div className="p-4 border-b">
          <h3 className="font-semibold mb-3">{t('contact_info')}</h3>
          
          <div className="space-y-3">
            <div>
              <label className="block text-sm text-gray-600 mb-1">{t('name')}</label>
              <input
                type="text"
                className="w-full p-2 border rounded"
                value={contactInfo.name}
                onChange={(e) => handleContactChange('name', e.target.value)}
                placeholder={t('enter_name')}
              />
            </div>
            
            <div>
              <label className="block text-sm text-gray-600 mb-1">{t('phone')}</label>
              <input
                type="tel"
                className={`w-full p-2 border rounded ${phoneError ? 'border-red-500' : ''}`}
                value={contactInfo.phone}
                onChange={(e) => handleContactChange('phone', e.target.value)}
                placeholder="+1234567890"
              />
              {phoneError && (
                <div className="text-red-500 text-sm mt-1">{phoneError}</div>
              )}
              <div className="text-xs text-gray-500 mt-1">
                {t('phone_format')}
              </div>
            </div>
          </div>
        </div>
      </div>
      
      {/* Summary and confirm button */}
      <div className="bg-white rounded-xl shadow-md p-4">
        {error && (
          <div className="mb-4 p-3 bg-red-100 text-red-700 rounded-lg">
            {error}
          </div>
        )}
        
        {quote && (
          <div className="flex justify-between items-center mb-4">
            <div className="text-gray-600">{t('seats_left')}: {quote.seats_left}</div>
            <div>
              <span className="text-gray-600">{t('total')}</span>
              <span className="text-xl font-bold ml-2">{fmtPrice(quote.total_net)}</span>
            </div>
          </div>
        )}
        
        <button 
          disabled={!quote || isSubmitting} 
          onClick={handleConfirm} 
          className="w-full py-3 bg-blue-600 text-white rounded-lg font-medium disabled:opacity-50"
        >
          {isSubmitting ? t('processing') : t('confirm')}
        </button>
      </div>
    </div>
  );
} 