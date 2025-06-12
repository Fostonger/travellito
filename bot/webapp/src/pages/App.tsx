// @ts-nocheck
import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import axios from 'axios';

interface Tour {
  id: number;
  title: string;
  price_net: string;
}

export default function App() {
  const [tours, setTours] = useState<Tour[]>([]);
  const [loading, setLoading] = useState(true);
  const apiBase = import.meta.env.VITE_API_BASE || 'http://localhost:8000/api/v1';

  useEffect(() => {
    const load = async () => {
      try {
        const { data } = await axios.get(`${apiBase}/tours/search`, {
          params: { limit: 20 },
          withCredentials: true,
        });
        setTours(data);
      } finally {
        setLoading(false);
      }
    };
    load();
  }, []);

  if (loading) return <p>Loading…</p>;

  return (
    <div style={{ padding: 16 }}>
      <h2>Available Tours</h2>
      <ul>
        {tours.map((t) => (
          <li key={t.id} style={{ margin: '12px 0' }}>
            <Link to={`/tour/${t.id}`}>{t.title}</Link> – {t.price_net} €
          </li>
        ))}
      </ul>
      <p>
        <Link to="/bookings">My Bookings</Link>
      </p>
    </div>
  );
} 