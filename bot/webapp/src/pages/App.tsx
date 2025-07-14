// @ts-nocheck
// src/pages/App.tsx
import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import axios from 'axios';
import { t, fmtPrice } from '../i18n';

interface Tour {
  id: number;
  title: string;
  price_net: string;
  category?: string;
  categories?: string[];
}

export default function App() {
  const [tours, setTours] = useState<Tour[]>([]);
  const [loading, setLoading] = useState(true);
  const apiBase =
    import.meta.env.VITE_API_BASE || 'https://api.trycloudflare.com/api/v1';

  useEffect(() => {
    (async () => {
      try {
        const { data } = await axios.get(`${apiBase}/public/tours/search`, {
          params: { limit: 50 },
          withCredentials: true,
        });
        setTours(data);
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen">
        <span className="animate-pulse text-gray-400">{t('loading')}</span>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 p-4">
      <h1 className="text-2xl font-extrabold text-cyan-700 mb-4">
        {t('available_tours')}
      </h1>

      {tours.length === 0 && (
        <p className="text-gray-500">{t('no_tours')}</p>
      )}

      <div className="grid gap-4 sm:grid-cols-2">
        {tours.map((tour) => (
          <Link
            key={tour.id}
            to={`/tour/${tour.id}`}
            className="block rounded-xl shadow hover:shadow-md transition bg-white"
          >
            <div className="p-4">
              <h2 className="font-semibold text-lg mb-2">{tour.title}</h2>
              <div className="flex flex-wrap gap-1 mb-2">
                {tour.categories && tour.categories.length > 0 ? (
                  // Show up to 3 categories with the new design
                  tour.categories.slice(0, 3).map((category, idx) => (
                    <span
                      key={idx}
                      className="inline-block px-2 py-0.5 text-xs rounded-full"
                      style={{ backgroundColor: pastelColor(category), color: '#333' }}
                    >
                      {category}
                    </span>
                  ))
                ) : tour.category ? (
                  // Fallback to legacy category
                  <span
                    className="inline-block px-2 py-0.5 text-xs rounded-full"
                    style={{ backgroundColor: pastelColor(tour.category), color: '#333' }}
                  >
                    {tour.category}
                  </span>
                ) : null}
                {tour.categories && tour.categories.length > 3 && (
                  <span className="inline-block px-2 py-0.5 text-xs rounded-full bg-gray-100 text-gray-500">
                    +{tour.categories.length - 3}
                  </span>
                )}
              </div>
              <p className="text-cyan-700 font-bold">
                {fmtPrice(tour.price_net)}
              </p>
            </div>
          </Link>
        ))}
      </div>

      <div className="mt-8">
        <Link
          to="/bookings"
          className="text-cyan-600 underline hover:text-cyan-800"
        >
          {t('my_bookings')}
        </Link>
      </div>
    </div>
  );
}

// Simple deterministic pastel color generator from string
function pastelColor(str: string): string {
  let hash = 0;
  for (let i = 0; i < str.length; i++) hash = str.charCodeAt(i) + ((hash << 5) - hash);
  const h = hash % 360;
  return `hsl(${h}, 70%, 85%)`;
}