// @ts-nocheck
import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { Link } from 'react-router-dom';
import { t, fmtPrice } from '../i18n';

export default function MyBookings() {
  const [bookings, setBookings] = useState([]);
  const apiBase = import.meta.env.VITE_API_BASE || 'http://localhost:8000/api/v1';

  const load = async () => {
    const { data } = await axios.get(`${apiBase}/bookings`, { params: { limit: 30 } });
    setBookings(data);
  };

  useEffect(() => {
    load();
  }, []);

  const handleCancel = async (id: number) => {
    await axios.patch(`${apiBase}/bookings/${id}`, { items: [] });
    await load();
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