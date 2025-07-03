// @ts-nocheck
import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { Link } from 'react-router-dom';
import { t, fmtPrice } from '../i18n';

export default function MyBookings() {
  const [bookings, setBookings] = useState([]);
  const apiBase = import.meta.env.VITE_API_BASE || 'http://localhost:8000/api/v1';

  const load = async () => {
    try {
      const { data } = await axios.get(`${apiBase}/bookings`, { 
        params: { limit: 30 },
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('authToken')}`
        }
      });
      setBookings(data);
    } catch (error) {
      console.error('Error loading bookings:', error);
      // If unauthorized, redirect to home page
      if (error.response?.status === 401) {
        alert('Please log in to view your bookings');
        window.location.href = '/';
      }
    }
  };

  useEffect(() => {
    load();
  }, []);

  const handleCancel = async (id: number) => {
    try {
      await axios.patch(`${apiBase}/bookings/${id}`, { items: [] }, {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('authToken')}`
        }
      });
      await load();
    } catch (error) {
      console.error('Error canceling booking:', error);
      if (error.response?.status === 401) {
        alert('Please log in to cancel bookings');
      } else {
        alert('Failed to cancel booking. Please try again.');
      }
    }
  };

  return (
    <div style={{ padding: 16 }}>
      <div className="mb-2">
        <Link to="/" className="text-cyan-600 underline">{t('back')}</Link>
      </div>
      <h2 className="text-xl font-bold mb-3">{t('my_bookings')}</h2>
      <ul>
        {bookings.map((b: any) => (
          <li key={b.id}>
            #{b.id} – {fmtPrice(b.amount)} &nbsp;
            <button onClick={() => handleCancel(b.id)}>{t('cancel')}</button>
          </li>
        ))}
      </ul>
    </div>
  );
} 