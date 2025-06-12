// @ts-nocheck
import React, { useEffect, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import axios from 'axios';

export default function Checkout() {
  const nav = useNavigate();
  const { state } = useLocation() as any;
  if (!state?.tourId || !state.departure) {
    return <p>Missing context</p>;
  }
  const tourId = state.tourId;
  const departure = state.departure;
  const apiBase = import.meta.env.VITE_API_BASE || 'http://localhost:8000/api/v1';

  const [categories, setCategories] = useState([]);
  const [quantities, setQuantities] = useState<any>({});
  const [quote, setQuote] = useState<any>(null);

  useEffect(() => {
    const load = async () => {
      const { data } = await axios.get(`${apiBase}/tours/${tourId}/categories`);
      setCategories(data);
    };
    load();
  }, [tourId]);

  const recalc = async (qs: any) => {
    const items = Object.entries(qs)
      .filter(([, qty]) => qty > 0)
      .map(([cid, qty]) => ({ category_id: Number(cid), qty }));
    if (!items.length) return setQuote(null);
    const { data } = await axios.post(`${apiBase}/quote`, {
      departure_id: departure.id,
      items,
    });
    setQuote(data);
  };

  const handleQtyChange = (cid: number, qty: number) => {
    const next = { ...quantities, [cid]: qty };
    setQuantities(next);
    recalc(next);
  };

  const handleConfirm = async () => {
    const items = Object.entries(quantities)
      .filter(([, qty]) => qty > 0)
      .map(([cid, qty]) => ({ category_id: Number(cid), qty }));
    await axios.post(`${apiBase}/bookings`, {
      departure_id: departure.id,
      items,
    });
    alert('Booking confirmed!');
    nav('/bookings');
  };

  return (
    <div style={{ padding: 16 }}>
      <h2>Checkout – {new Date(departure.starts_at).toLocaleString()}</h2>
      {categories.map((c: any) => (
        <div key={c.id} style={{ marginBottom: 8 }}>
          {c.name} – {c.price_net} € &times;{' '}
          <input
            type="number"
            min="0"
            style={{ width: 60 }}
            value={quantities[c.id] || ''}
            onChange={(e) => handleQtyChange(c.id, Number(e.target.value))}
          />
        </div>
      ))}
      {quote && (
        <p>
          <strong>Total:</strong> {quote.total_net} € – seats left: {quote.seats_left}
        </p>
      )}
      <button disabled={!quote} onClick={handleConfirm}>
        Confirm Booking
      </button>
    </div>
  );
} 