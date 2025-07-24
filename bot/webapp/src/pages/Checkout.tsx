// @ts-nocheck
import React, { useEffect, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import axios from 'axios';
import { ChevronLeft, Calendar, Clock, User, Phone, AlertTriangle } from 'lucide-react';
import { t, fmtPrice } from '../i18n';
import { formatTime, formatFullDate, getDepartureDate } from '../utils/dateUtils';
import { parsePhoneNumber, isValidPhoneNumber } from 'libphonenumber-js';
import { Layout } from '../components/Layout';
import { Button } from '../components/ui/button';
import { Card } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { Separator } from '../components/ui/separator';

export default function Checkout() {
  const nav = useNavigate();
  const { state } = useLocation() as any;
  if (!state?.tourId || !state.departure) {
    return (
      <Layout>
        <div className="flex justify-center items-center h-64">
          <p className="text-lg text-muted-foreground">{t('missing_ctx')}</p>
        </div>
      </Layout>
    );
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
    <Layout>
      <div className="space-y-6">
        <div className="flex items-center">
          <Button 
            variant="ghost" 
            size="sm" 
            className="gap-1"
            onClick={() => nav(-1)}
          >
            <ChevronLeft className="h-4 w-4" />
            {t('back')}
          </Button>
        </div>
        
        <Card className="overflow-hidden">
          <div className="bg-primary p-4 text-primary-foreground">
            <h1 className="text-xl font-bold">{t('checkout').replace('{date}', departureTime)}</h1>
            <p className="text-primary-foreground/80">{departureDate}</p>
          </div>
          
          {/* Ticket selection */}
          <div className="p-6 border-b">
            <h2 className="font-semibold mb-4">{t('select_tickets')}</h2>
            
            <div className="space-y-4">
              {categories.map((c: any) => (
                <div key={c.id} className="flex items-center justify-between border-b pb-4">
                  <div>
                    <div className="font-medium">{c.name}</div>
                    <div className="text-primary font-semibold">{fmtPrice(c.price_net)}</div>
                  </div>
                  <div className="flex items-center gap-2">
                    <Button 
                      variant="outline" 
                      size="icon"
                      className="h-8 w-8 rounded-full"
                      onClick={() => handleQtyChange(c.id, Math.max(0, (quantities[c.id] || 0) - 1))}
                    >
                      -
                    </Button>
                    <span className="w-8 text-center font-medium">
                      {quantities[c.id] || 0}
                    </span>
                    <Button 
                      variant="default" 
                      size="icon"
                      className="h-8 w-8 rounded-full"
                      onClick={() => handleQtyChange(c.id, (quantities[c.id] || 0) + 1)}
                    >
                      +
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          </div>
          
          {/* Contact information */}
          <div className="p-6">
            <h2 className="font-semibold mb-4">{t('contact_info')}</h2>
            
            <div className="space-y-4">
              <div>
                <label className="block text-sm text-muted-foreground mb-1">{t('name')}</label>
                <div className="relative">
                  <User className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                  <input
                    type="text"
                    className="w-full p-2 pl-10 border rounded-md"
                    value={contactInfo.name}
                    onChange={(e) => handleContactChange('name', e.target.value)}
                    placeholder={t('enter_name')}
                  />
                </div>
              </div>
              
              <div>
                <label className="block text-sm text-muted-foreground mb-1">{t('phone')}</label>
                <div className="relative">
                  <Phone className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                  <input
                    type="tel"
                    className={`w-full p-2 pl-10 border rounded-md ${phoneError ? 'border-destructive' : ''}`}
                    value={contactInfo.phone}
                    onChange={(e) => handleContactChange('phone', e.target.value)}
                    placeholder="+1234567890"
                  />
                </div>
                {phoneError && (
                  <div className="text-destructive text-sm mt-1">{phoneError}</div>
                )}
                <div className="text-xs text-muted-foreground mt-1">
                  {t('phone_format')}
                </div>
              </div>
            </div>
            
            <Separator className="my-6" />
            
            {error && (
              <div className="mb-6 p-4 bg-destructive/10 border border-destructive/30 text-destructive rounded-lg flex items-start gap-3">
                <AlertTriangle className="h-5 w-5 mt-0.5 flex-shrink-0" />
                <div>{error}</div>
              </div>
            )}
            
            {quote && (
              <div className="flex justify-between items-center mb-6">
                <div className="text-muted-foreground">{t('seats_left')}: {quote.seats_left}</div>
                <div className="text-right">
                  <div className="text-sm text-muted-foreground">{t('total')}</div>
                  <div className="text-xl font-bold">{fmtPrice(quote.total_net)}</div>
                </div>
              </div>
            )}
            
            <Button 
              disabled={!quote || isSubmitting} 
              onClick={handleConfirm} 
              className="w-full"
            >
              {isSubmitting ? t('processing') : t('confirm')}
            </Button>
          </div>
        </Card>
      </div>
    </Layout>
  );
} 