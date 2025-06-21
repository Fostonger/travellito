// @ts-nocheck
import React, { useEffect, useState } from 'react';
import { useParams, Link, useNavigate } from 'react-router-dom';
import axios from 'axios';
import { t, fmtPrice } from '../i18n';

export default function TourDetail() {
  const { id } = useParams();
  const nav = useNavigate();
  const apiBase = import.meta.env.VITE_API_BASE || 'http://localhost:8000/api/v1';
  const [tour, setTour] = useState(null);
  const [departures, setDepartures] = useState([]);
  const [loading, setLoading] = useState(true);
  const [imgIdx, setImgIdx] = useState(0);

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

  const nextImg = () => setImgIdx((imgIdx + 1) % (tour.images?.length || 1));
  const prevImg = () => setImgIdx((imgIdx - 1 + (tour.images?.length || 1)) % (tour.images?.length || 1));

  if (loading) return <p>{t('loading')}</p>;
  if (!tour) return <p>{t('not_found')}</p>;

  return (
    <div className="p-4">
      {/* Back link */}
      <div className="mb-2">
        <Link to="/" className="text-cyan-600 underline">{t('back')}</Link>
      </div>

      {/* Image carousel */}
      {tour.images?.length > 0 && (
        <div className="relative mb-4">
          <img
            src={tour.images[imgIdx]}
            className="w-full h-60 object-cover rounded-xl"
          />
          {tour.images.length > 1 && (
            <>
              <button
                className="absolute left-2 top-1/2 -translate-y-1/2 bg-white/70 rounded-full p-2"
                onClick={prevImg}
              >◀</button>
              <button
                className="absolute right-2 top-1/2 -translate-y-1/2 bg-white/70 rounded-full p-2"
                onClick={nextImg}
              >▶</button>
            </>
          )}
        </div>
      )}

      <h2 className="text-xl font-bold mb-1">{tour.title}</h2>
      {tour.category && (
        <span
          className="inline-block px-2 py-1 text-xs rounded-full mb-2"
          style={{ backgroundColor: pastelColor(tour.category), color: '#333' }}
        >
          {tour.category}
        </span>
      )}

      <p className="mb-4 text-gray-700 whitespace-pre-line">{tour.description}</p>
      <h3>{t('upcoming_departures')}</h3>
      <ul>
        {departures.map((d: any) => (
          <li key={d.id}>
            {new Date(d.starts_at).toLocaleString()} – {t('seats_left')}: {d.seats_left}{' '}
            <button onClick={() => nav('/checkout', { state: { tourId: id, departure: d } })}>{t('book')}</button>
          </li>
        ))}
      </ul>
    </div>
  );
}

function pastelColor(str: string): string {
  let hash = 0;
  for (let i = 0; i < str.length; i++) hash = str.charCodeAt(i) + ((hash << 5) - hash);
  const h = hash % 360;
  return `hsl(${h}, 70%, 85%)`;
} 