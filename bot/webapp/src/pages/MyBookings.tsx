// @ts-nocheck
import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { CalendarX, CalendarCheck, MapPin, Clock, AlertTriangle } from 'lucide-react';
import { t, fmtPrice } from '../i18n';
import { formatDate, formatTime } from '../utils/dateUtils';
import { Layout } from '../components/Layout';
import { Button } from '../components/ui/button';
import { Skeleton } from '../components/ui/skeleton';
import { Badge } from '../components/ui/badge';
import { Card } from '../components/ui/card';

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
  const [cancelingId, setCancelingId] = useState<number | null>(null);
  
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
      setCancelingId(id);
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
    } finally {
      setCancelingId(null);
    }
  };

  // Format date and time for display
  const formatDateTime = (dateTimeString: string) => {
    return {
      date: formatDate(dateTimeString),
      time: formatTime(dateTimeString)
    };
  };

  // Get total tickets count
  const getTicketsSummary = (booking: Booking) => {
    return booking.items.reduce((total, item) => total + item.qty, 0);
  };

  // Filter bookings by upcoming/past
  const now = new Date();
  const upcomingBookings = bookings.filter(b => new Date(b.departure_date) >= now);
  const pastBookings = bookings.filter(b => new Date(b.departure_date) < now);

  return (
    <Layout>
      <div className="space-y-6">
        <h1 className="text-2xl font-bold">{t('my_bookings')}</h1>
        
        {error && (
          <div className="bg-destructive/10 border border-destructive/30 text-destructive rounded-lg p-4 flex items-start gap-3">
            <AlertTriangle className="h-5 w-5 mt-0.5 flex-shrink-0" />
            <div>
              <div className="font-semibold">{t('error')}</div>
              <div>{error}</div>
            </div>
          </div>
        )}
        
        {loading ? (
          <BookingsSkeleton />
        ) : bookings.length === 0 ? (
          <EmptyState 
            emoji="📅" 
            title={t('no_bookings')}
            description={t('no_bookings')}
          />
        ) : (
          <div className="space-y-6">
            {/* Tabs */}
            <div className="flex border-b">
              <button
                className={`px-4 py-2 font-medium border-b-2 ${
                  activeTab === "upcoming" 
                    ? "border-primary text-primary" 
                    : "border-transparent hover:border-gray-200"
                }`}
                onClick={() => setActiveTab("upcoming")}
              >
                {t('tab_upcoming')} ({upcomingBookings.length})
              </button>
              <button
                className={`px-4 py-2 font-medium border-b-2 ${
                  activeTab === "past" 
                    ? "border-primary text-primary" 
                    : "border-transparent hover:border-gray-200"
                }`}
                onClick={() => setActiveTab("past")}
              >
                {t('tab_past')} ({pastBookings.length})
              </button>
            </div>
            
            {/* Bookings list */}
            {activeTab === "upcoming" && (
              upcomingBookings.length === 0 ? (
                <EmptyState 
                  emoji="🗓️" 
                  title={t('no_upcoming_bookings')}
                  description={t('no_upcoming_bookings')}
                />
              ) : (
                <div className="space-y-4">
                  {upcomingBookings.map(booking => (
                    <BookingCard 
                      key={booking.id} 
                      booking={booking} 
                      onCancel={handleCancel} 
                      isCanceling={cancelingId === booking.id}
                      formatDateTime={formatDateTime}
                      getTicketsSummary={getTicketsSummary}
                    />
                  ))}
                </div>
              )
            )}
            
            {activeTab === "past" && (
              pastBookings.length === 0 ? (
                <EmptyState 
                  emoji="📆" 
                  title={t('no_past_bookings')}
                  description={t('no_past_bookings')}
                />
              ) : (
                <div className="space-y-4">
                  {pastBookings.map(booking => (
                    <BookingCard 
                      key={booking.id} 
                      booking={booking} 
                      isPast
                      formatDateTime={formatDateTime}
                      getTicketsSummary={getTicketsSummary}
                    />
                  ))}
                </div>
              )
            )}
          </div>
        )}
      </div>
    </Layout>
  );
}

interface BookingCardProps {
  booking: Booking;
  onCancel?: (bookingId: number) => void;
  isCanceling?: boolean;
  isPast?: boolean;
  formatDateTime: (dateString: string) => { date: string; time: string };
  getTicketsSummary: (booking: Booking) => number;
}

const BookingCard = ({ 
  booking, 
  onCancel, 
  isCanceling = false,
  isPast = false,
  formatDateTime, 
  getTicketsSummary 
}: BookingCardProps) => {
  const [showConfirm, setShowConfirm] = useState(false);
  
  const { date, time } = formatDateTime(booking.departure_date);
  const ticketsCount = getTicketsSummary(booking);
  
  return (
    <Card className="overflow-hidden">
      <div className="p-4 border-b bg-muted/20">
        <h3 className="font-semibold text-lg">{booking.tour_title}</h3>
        <div className="flex flex-wrap gap-4 mt-2 text-sm text-muted-foreground">
          <div className="flex items-center gap-1">
            <Clock className="h-4 w-4" />
            <span>{date} • {time}</span>
          </div>
          {booking.tour_address && (
            <div className="flex items-center gap-1">
              <MapPin className="h-4 w-4" />
              <span className="truncate max-w-xs">{booking.tour_address}</span>
            </div>
          )}
        </div>
      </div>
      
      <div className="p-4">
        <div className="flex justify-between items-center mb-3">
          <div className="text-sm">
            <span className="text-muted-foreground">{t('total_tickets')}:</span> {ticketsCount}
          </div>
          <div>
            <span className="text-muted-foreground mr-1">{t('total')}:</span>
            <span className="font-semibold">{fmtPrice(booking.amount)}</span>
          </div>
        </div>
        
        {booking.items.length > 0 && (
          <div className="text-sm space-y-1 mb-4 text-muted-foreground">
            {booking.items.map((item, idx) => (
              <div key={idx} className="flex justify-between">
                <span>{item.category_name} × {item.qty}</span>
                <span>{fmtPrice(item.amount)}</span>
              </div>
            ))}
          </div>
        )}
        
        {showConfirm ? (
          <div className="bg-amber-50 border border-amber-200 rounded-lg p-3 mb-3">
            <p className="text-amber-800 font-medium mb-2">{t('confirm_cancel_title')}</p>
            <p className="text-sm text-amber-700 mb-3">{t('confirm_cancel_description')}</p>
            <div className="flex gap-2">
              <Button 
                variant="destructive"
                size="sm"
                className="flex-1"
                onClick={() => {
                  onCancel?.(booking.id);
                  setShowConfirm(false);
                }}
                disabled={isCanceling}
              >
                {isCanceling ? t('processing') : t('yes_cancel')}
              </Button>
              <Button 
                variant="outline"
                size="sm"
                className="flex-1"
                onClick={() => setShowConfirm(false)}
              >
                {t('no_keep')}
              </Button>
            </div>
          </div>
        ) : (
          booking.is_cancellable && !isPast && (
            <Button 
              variant="outline" 
              className="w-full text-destructive border-destructive/30 hover:bg-destructive/10"
              onClick={() => setShowConfirm(true)}
            >
              {t('cancel')}
            </Button>
          )
        )}
      </div>
    </Card>
  );
};

interface EmptyStateProps {
  emoji: string;
  title: string;
  description: string;
  action?: React.ReactNode;
}

const EmptyState = ({ emoji, title, description, action }: EmptyStateProps) => (
  <div className="bg-card rounded-lg shadow-sm p-8 text-center">
    <div className="text-4xl mb-4">{emoji}</div>
    <h3 className="text-xl font-medium mb-2">{title}</h3>
    <p className="text-muted-foreground mb-4">{description}</p>
    {action}
  </div>
);

const BookingsSkeleton = () => (
  <div className="space-y-6">
    <div className="flex border-b">
      <Skeleton className="h-10 w-32 mx-2" />
      <Skeleton className="h-10 w-32 mx-2" />
    </div>
    
    <div className="space-y-4">
      {[1, 2, 3].map(i => (
        <div key={i} className="bg-card rounded-lg shadow-sm overflow-hidden">
          <div className="p-4 border-b">
            <Skeleton className="h-6 w-3/4 mb-2" />
            <div className="flex gap-4">
              <Skeleton className="h-4 w-32" />
              <Skeleton className="h-4 w-40" />
            </div>
          </div>
          <div className="p-4">
            <div className="flex justify-between mb-3">
              <Skeleton className="h-5 w-24" />
              <Skeleton className="h-5 w-24" />
            </div>
            <div className="space-y-1 mb-4">
              <Skeleton className="h-4 w-full" />
              <Skeleton className="h-4 w-full" />
            </div>
            <Skeleton className="h-9 w-full" />
          </div>
        </div>
      ))}
    </div>
  </div>
); 