// @ts-nocheck
import React, { useEffect, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import axios from 'axios';
import { t, fmtPrice } from '../i18n';

export default function Checkout() {
  const nav = useNavigate();
  const { state } = useLocation() as any;
  if (!state?.tourId || !state.departure) {
    return <p>{t('missing_ctx')}</p>;
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
    alert(t('booking_confirmed'));
    nav('/bookings');
  };

  return (
    <div className="p-4">
      <div className="mb-2">
        <button onClick={() => nav(-1)} className="text-cyan-600 underline">{t('back')}</button>
      </div>
      <h2 className="text-xl font-bold mb-3">{t('checkout', { date: new Date(departure.starts_at).toLocaleString() })}</h2>
      {categories.map((c: any) => (
        <div key={c.id} style={{ marginBottom: 8 }}>
          {c.name} – {fmtPrice(c.price_net)} &times;{' '}
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
          <strong>{t('total')}</strong> {fmtPrice(quote.total_net)} – {t('seats_left')}: {quote.seats_left}
        </p>
      )}
      <button disabled={!quote} onClick={handleConfirm} className="mt-4 px-4 py-2 bg-cyan-600 text-white rounded disabled:opacity-50">
        {t('confirm')}
      </button>
    </div>
  );
} 