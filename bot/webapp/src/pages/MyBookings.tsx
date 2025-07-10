// @ts-nocheck
import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { Link } from 'react-router-dom';
import { t, fmtPrice } from '../i18n';
import { format, parseISO } from 'date-fns';
import { ru, enUS } from 'date-fns/locale';

// Shadcn UI components
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "../components/ui/card";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { Separator } from "../components/ui/separator";
import { ScrollArea } from "../components/ui/scroll-area";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "../components/ui/tabs";
import { Skeleton } from "../components/ui/skeleton";
import { AlertCircle, Calendar, Clock, CheckCircle, XCircle, AlertTriangle } from 'lucide-react';
import { Alert, AlertDescription, AlertTitle } from "../components/ui/alert";

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
}

// Get current locale
const getCurrentLocale = () => {
  // Get language from browser or use default
  const language = navigator.language || 'en-US';
  return language.startsWith('ru') ? ru : enUS;
};

// Helper function for status badges - moved outside of component
const getStatusBadge = (status: string) => {
  switch (status) {
    case 'confirmed':
      return <Badge className="bg-green-500 text-white"><CheckCircle className="w-3 h-3 mr-1" /> {t('status_confirmed')}</Badge>;
    case 'rejected':
      return <Badge className="bg-red-500 text-white"><XCircle className="w-3 h-3 mr-1" /> {t('status_rejected')}</Badge>;
    case 'cancelled':
      return <Badge className="bg-gray-500 text-white"><XCircle className="w-3 h-3 mr-1" /> {t('status_cancelled')}</Badge>;
    default:
      return <Badge className="bg-yellow-500 text-black"><AlertCircle className="w-3 h-3 mr-1" /> {t('status_pending')}</Badge>;
  }
};

// Helper functions for date formatting - moved outside of component
const formatDate = (dateString: string) => {
  try {
    const date = parseISO(dateString);
    return format(date, 'PP', { locale: getCurrentLocale() });
  } catch (e) {
    return dateString;
  }
};

const formatTime = (dateString: string) => {
  try {
    // Parse the ISO string and convert from UTC to local timezone
    const date = parseISO(dateString);
    const localDate = new Date(date.getTime() - (date.getTimezoneOffset() * 60000));
    // Use 24-hour format (HH:mm)
    return format(localDate, 'HH:mm', { locale: getCurrentLocale() });
  } catch (e) {
    return '';
  }
};

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
      setBookings(data);
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
      <div className="min-h-screen bg-white text-black p-4 space-y-4">
        <div className="flex items-center mb-4">
          <Link to="/" className="text-blue-600 hover:underline">
            {t('back')}
          </Link>
        </div>
        <h2 className="text-2xl font-bold">{t('my_bookings')}</h2>
        {[1, 2, 3].map(i => (
          <Card key={i} className="bg-gray-50 border-gray-200">
            <CardHeader>
              <Skeleton className="h-6 w-3/4" />
            </CardHeader>
            <CardContent>
              <div className="space-y-2">
                <Skeleton className="h-4 w-1/2" />
                <Skeleton className="h-4 w-1/4" />
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-white text-black p-4 max-w-md mx-auto">
      <div className="flex items-center mb-4">
        <Link to="/" className="text-blue-600 hover:underline">
          {t('back')}
        </Link>
      </div>
      
      <h2 className="text-2xl font-bold mb-4">{t('my_bookings')}</h2>
      
      {error && (
        <Alert variant="destructive" className="mb-4 bg-red-50 border-red-300 text-red-800">
          <AlertCircle className="h-4 w-4" />
          <AlertTitle>{t('error')}</AlertTitle>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {bookings.length === 0 ? (
        <Card className="bg-gray-50 border-gray-200">
          <CardContent className="pt-6 text-center text-gray-600">
            {t('no_bookings')}
          </CardContent>
        </Card>
      ) : (
        <Tabs defaultValue="upcoming" value={activeTab} onValueChange={setActiveTab}>
          <TabsList className="grid w-full grid-cols-2 bg-gray-100">
            <TabsTrigger value="upcoming" className="data-[state=active]:bg-white data-[state=active]:text-black">
              {t('tab_upcoming')} ({upcomingBookings.length})
            </TabsTrigger>
            <TabsTrigger value="past" className="data-[state=active]:bg-white data-[state=active]:text-black">
              {t('tab_past')} ({pastBookings.length})
            </TabsTrigger>
          </TabsList>
          
          <TabsContent value="upcoming" className="mt-4 space-y-4">
            {upcomingBookings.length === 0 ? (
              <Card className="bg-gray-50 border-gray-200">
                <CardContent className="pt-6 text-center text-gray-600">
                  {t('no_upcoming_bookings')}
                </CardContent>
              </Card>
            ) : (
              <ScrollArea className="h-[calc(100vh-220px)]">
                <div className="space-y-4">
                  {upcomingBookings.map(booking => (
                    <BookingCard 
                      key={booking.id} 
                      booking={booking} 
                      onCancel={handleCancel} 
                    />
                  ))}
                </div>
              </ScrollArea>
            )}
          </TabsContent>
          
          <TabsContent value="past" className="mt-4 space-y-4">
            {pastBookings.length === 0 ? (
              <Card className="bg-gray-50 border-gray-200">
                <CardContent className="pt-6 text-center text-gray-600">
                  {t('no_past_bookings')}
                </CardContent>
              </Card>
            ) : (
              <ScrollArea className="h-[calc(100vh-220px)]">
                <div className="space-y-4">
                  {pastBookings.map(booking => (
                    <BookingCard 
                      key={booking.id} 
                      booking={booking} 
                      onCancel={handleCancel}
                      isPast
                    />
                  ))}
                </div>
              </ScrollArea>
            )}
          </TabsContent>
        </Tabs>
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
  return (
    <Card className="overflow-hidden bg-gray-50 border-gray-200">
      <CardHeader className="pb-2 bg-white">
        <div className="flex justify-between items-start">
          <CardTitle className="text-lg text-black">{booking.tour_title}</CardTitle>
          {getStatusBadge(booking.status)}
        </div>
        <CardDescription className="flex items-center gap-1 mt-1 text-gray-700">
          <Calendar className="h-3 w-3" />
          {formatDate(booking.departure_date)}
          <span className="mx-1">•</span>
          <Clock className="h-3 w-3" />
          {formatTime(booking.departure_date)}
        </CardDescription>
      </CardHeader>
      
      <CardContent className="pb-3 text-black">
        {booking.items.length > 0 && (
          <div className="text-sm space-y-1 mb-2">
            {booking.items.map((item, idx) => (
              <div key={idx} className="flex justify-between">
                <span>{item.category_name} × {item.qty}</span>
                <span className="font-medium">{fmtPrice(item.amount)}</span>
              </div>
            ))}
            <Separator className="my-2 bg-gray-300" />
            <div className="flex justify-between font-medium">
              <span>{t('total')}</span>
              <span className="text-blue-700">{fmtPrice(booking.amount)}</span>
            </div>
          </div>
        )}
      </CardContent>
      
      {booking.is_cancellable && !isPast && (
        <CardFooter className="pt-0 bg-white">
          <Button 
            variant="destructive" 
            size="sm" 
            className="w-full bg-red-600 hover:bg-red-700 text-white"
            onClick={() => onCancel(booking.id)}
          >
            {t('cancel')}
          </Button>
        </CardFooter>
      )}
    </Card>
  );
} 