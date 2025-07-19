// @ts-nocheck
import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { Link } from 'react-router-dom';
import { t, fmtPrice } from '../i18n';
import { formatDate, formatTime } from '../utils/dateUtils';

// Types
interface BookingItem {
  category_name: string;
  qty: number;
  amount: number;
}

interface Booking {
  id: number;
  amount: number;
  status: string;
  created: string;
  departure_date: string;
  tour_title: string;
  tour_id: number;
  departure_id: number;
  is_cancellable: boolean;
  items: BookingItem[];
  tour_address?: string;
}

export default function MyBookings() {
  const [bookings, setBookings] = useState<Booking[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState("upcoming");
  
  const apiBase = import.meta.env.VITE_API_BASE || 'http://localhost:8000/api/v1';

  const load = async () => {
    try {
      setLoading(true);
      const { data } = await axios.get(`${apiBase}/bookings/tourist`, { 
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('authToken')}`
        }
      });
      // Filter out cancelled bookings
      const activeBookings = data.filter(booking => booking.status.toLowerCase() !== "cancelled");
      setBookings(activeBookings);
      setError(null);
    } catch (err: any) {
      console.error('Error loading bookings:', err);
      setError(err.response?.data?.error || t('error_loading_bookings'));
      // If unauthorized, redirect to home page
      if (err.response?.status === 401) {
        alert(t('error_unauthorized'));
        window.location.href = '/';
      }
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const handleCancel = async (id: number) => {
    try {
      await axios.patch(`${apiBase}/bookings/tourist/${id}/cancel`, {}, {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('authToken')}`
        }
      });
      await load();
    } catch (err: any) {
      console.error('Error canceling booking:', err);
      setError(err.response?.data?.error || t('error_canceling_booking'));
      if (err.response?.status === 401) {
        alert(t('error_unauthorized'));
      }
    }
  };

  // Filter bookings by upcoming/past
  const now = new Date();
  const upcomingBookings = bookings.filter(b => new Date(b.departure_date) >= now);
  const pastBookings = bookings.filter(b => new Date(b.departure_date) < now);

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 p-4 space-y-4">
        <div className="flex items-center mb-4">
          <Link to="/" className="text-blue-600 hover:underline">
            {t('back')}
          </Link>
        </div>
        <h2 className="text-2xl font-bold text-cyan-700">{t('my_bookings')}</h2>
        {[1, 2, 3].map(i => (
          <div key={i} className="bg-white rounded-xl shadow-md p-4 mb-4 animate-pulse">
            <div className="h-6 bg-gray-200 rounded w-3/4 mb-3"></div>
            <div className="h-4 bg-gray-200 rounded w-1/2 mb-2"></div>
            <div className="h-4 bg-gray-200 rounded w-1/3"></div>
          </div>
        ))}
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 p-4 pb-20 max-w-md mx-auto">
      <div className="flex items-center mb-4">
        <Link to="/" className="text-blue-600 hover:underline flex items-center">
          <span className="mr-1">←</span> {t('back')}
        </Link>
      </div>
      
      <h2 className="text-2xl font-bold mb-4 text-cyan-700">{t('my_bookings')}</h2>
      
      {error && (
        <div className="mb-4 p-3 bg-red-100 border border-red-300 text-red-800 rounded-lg">
          <div className="font-bold">{t('error')}</div>
          <div>{error}</div>
        </div>
      )}

      {bookings.length === 0 ? (
        <div className="bg-white rounded-xl shadow-md p-6 text-center text-gray-600">
          {t('no_bookings')}
        </div>
      ) : (
        <div>
          <div className="grid grid-cols-2 gap-1 bg-white rounded-lg shadow-sm mb-4">
            <button 
              className={`py-2 rounded-lg font-medium text-center ${
                activeTab === "upcoming" ? "bg-blue-600 text-white" : "bg-gray-100 text-gray-700"
              }`}
              onClick={() => setActiveTab("upcoming")}
            >
              {t('tab_upcoming')} ({upcomingBookings.length})
            </button>
            <button 
              className={`py-2 rounded-lg font-medium text-center ${
                activeTab === "past" ? "bg-blue-600 text-white" : "bg-gray-100 text-gray-700"
              }`}
              onClick={() => setActiveTab("past")}
            >
              {t('tab_past')} ({pastBookings.length})
            </button>
          </div>
          
          {activeTab === "upcoming" && (
            <div className="space-y-4">
              {upcomingBookings.length === 0 ? (
                <div className="bg-white rounded-xl shadow-md p-6 text-center text-gray-600">
                  {t('no_upcoming_bookings')}
                </div>
              ) : (
                <div className="space-y-4" style={{ maxHeight: 'calc(100vh - 220px)', overflowY: 'auto' }}>
                  {upcomingBookings.map(booking => (
                    <BookingCard 
                      key={booking.id} 
                      booking={booking} 
                      onCancel={handleCancel} 
                    />
                  ))}
                </div>
              )}
            </div>
          )}
          
          {activeTab === "past" && (
            <div className="space-y-4">
              {pastBookings.length === 0 ? (
                <div className="bg-white rounded-xl shadow-md p-6 text-center text-gray-600">
                  {t('no_past_bookings')}
                </div>
              ) : (
                <div className="space-y-4" style={{ maxHeight: 'calc(100vh - 220px)', overflowY: 'auto' }}>
                  {pastBookings.map(booking => (
                    <BookingCard 
                      key={booking.id} 
                      booking={booking} 
                      onCancel={handleCancel}
                      isPast
                    />
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

interface BookingCardProps {
  booking: Booking;
  onCancel: (id: number) => void;
  isPast?: boolean;
}

function BookingCard({ booking, onCancel, isPast = false }: BookingCardProps) {
  const [showConfirm, setShowConfirm] = useState(false);
  
  const handleCancelClick = () => {
    setShowConfirm(true);
  };
  
  const confirmCancel = () => {
    onCancel(booking.id);
    setShowConfirm(false);
  };
  
  const cancelAction = () => {
    setShowConfirm(false);
  };
  
  return (
    <div className="bg-white rounded-xl shadow-sm overflow-hidden border border-gray-100">
      <div className="p-4 bg-gradient-to-r from-blue-50 to-white">
        <h3 className="text-lg font-semibold text-gray-800">{booking.tour_title}</h3>
        <div className="flex items-center text-sm text-gray-600 mt-1">
          <span className="mr-1">🗓️</span>
          {formatDate(booking.departure_date)}
          <span className="mx-1.5">•</span>
          <span className="mr-1">🕒</span>
          {formatTime(booking.departure_date)}
        </div>
        {booking.tour_address && (
          <div className="flex text-sm text-gray-600 mt-1.5">
            <span className="mr-1 flex-shrink-0">📍</span>
            <span className="line-clamp-2">{booking.tour_address}</span>
          </div>
        )}
      </div>
      
      <div className="px-4 py-3">
        {booking.items.length > 0 && (
          <div className="space-y-1.5">
            {booking.items.map((item, idx) => (
              <div key={idx} className="flex justify-between text-sm">
                <span className="text-gray-700">{item.category_name} × {item.qty}</span>
                <span className="font-medium text-gray-900">{fmtPrice(item.amount)}</span>
              </div>
            ))}
            <div className="border-t border-gray-100 my-2"></div>
            <div className="flex justify-between items-center">
              <span className="font-medium text-gray-700">{t('total')}</span>
              <span className="text-lg font-bold text-blue-600">{fmtPrice(booking.amount)}</span>
            </div>
          </div>
        )}
        
        {showConfirm && (
          <div className="mt-4 p-3 bg-yellow-50 border border-yellow-200 text-yellow-800 rounded-lg">
            <div className="font-medium mb-1">❓ {t('confirm_cancel_title')}</div>
            <div className="text-sm mb-3">{t('confirm_cancel_description')}</div>
            <div className="flex gap-2">
              <button 
                className="px-4 py-2 bg-red-600 hover:bg-red-700 text-white text-sm font-medium rounded-lg flex-1"
                onClick={confirmCancel}
              >
                {t('yes_cancel')}
              </button>
              <button 
                className="px-4 py-2 bg-gray-100 hover:bg-gray-200 text-gray-700 text-sm font-medium rounded-lg border border-gray-200 flex-1"
                onClick={cancelAction}
              >
                {t('no_keep')}
              </button>
            </div>
          </div>
        )}
      </div>
      
      {booking.is_cancellable && !isPast && !showConfirm && (
        <div className="px-4 pb-4">
          <button 
            className="w-full py-2.5 bg-white border border-red-500 text-red-600 hover:bg-red-50 rounded-lg text-sm font-medium"
            onClick={handleCancelClick}
          >
            {t('cancel')}
          </button>
        </div>
      )}
    </div>
  );
} 