// @ts-nocheck
import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { Link } from 'react-router-dom';

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
      <h2>My Bookings</h2>
      <ul>
        {bookings.map((b: any) => (
          <li key={b.id}>
            #{b.id} – {b.amount} € &nbsp;
            <button onClick={() => handleCancel(b.id)}>Cancel</button>
          </li>
        ))}
      </ul>
      <p>
        <Link to="/">Back</Link>
      </p>
    </div>
  );
} 