// @ts-nocheck
import React, { useEffect, useState } from 'react';
import { useParams, Link, useNavigate } from 'react-router-dom';
import axios from 'axios';

export default function TourDetail() {
  const { id } = useParams();
  const nav = useNavigate();
  const apiBase = import.meta.env.VITE_API_BASE || 'http://localhost:8000/api/v1';
  const [tour, setTour] = useState(null);
  const [departures, setDepartures] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const load = async () => {
      if (!id) return;
      const [tourRes, depRes] = await Promise.all([
        axios.get(`${apiBase}/tours/${id}`),
        axios.get(`${apiBase}/tours/${id}/departures`, { params: { limit: 10 } }),
      ]);
      setTour(tourRes.data);
      setDepartures(depRes.data);
      setLoading(false);
    };
    load();
  }, [id]);

  if (loading) return <p>Loading…</p>;
  if (!tour) return <p>Not found</p>;

  return (
    <div style={{ padding: 16 }}>
      <h2>{tour.title}</h2>
      <p>{tour.description}</p>
      <h3>Upcoming departures</h3>
      <ul>
        {departures.map((d: any) => (
          <li key={d.id}>
            {new Date(d.starts_at).toLocaleString()} – seats left: {d.seats_left}{' '}
            <button onClick={() => nav('/checkout', { state: { tourId: id, departure: d } })}>Book</button>
          </li>
        ))}
      </ul>
      <p>
        <Link to="/">Back</Link>
      </p>
    </div>
  );
} 