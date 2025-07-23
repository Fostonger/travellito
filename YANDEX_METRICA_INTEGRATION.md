# Yandex Metrica Analytics Integration

This document explains how Yandex Metrica analytics has been integrated into the Travellito platform.

## 1. Overview

The integration consists of two main components:
- Frontend JavaScript tracking (tag-based)
- Backend Measurement Protocol tracking

Both components use the same Yandex Metrica counter ID, and the backend also uses a Measurement Protocol token for server-side events.

## 2. Configuration

### Environment Variables

**Frontend (.env.front or similar)**
```dotenv
VITE_METRIKA_COUNTER=97240127
```

**Backend (.env)**
```dotenv
METRIKA_COUNTER=97240127
METRIKA_MP_TOKEN=ca4c...91a7d
```

## 3. Frontend Implementation

### 3.1 Tracking Script

The Yandex Metrica script is loaded in `bot/webapp/index.html`:

```html
<!-- Yandex.Metrika counter -->
<script type="text/javascript">
  (function(m,e,t,r,i,k,a){
    m[i]=m[i]||function(){(m[i].a=m[i].a||[]).push(arguments)};
    m[i].l=1*new Date();
    k=e.createElement(t),a=e.getElementsByTagName(t)[0];
    k.async=1;k.src=r;a.parentNode.insertBefore(k,a)
  })(window,document,"script","https://mc.yandex.ru/metrika/tag.js","ym");

  window.METRIKA_COUNTER = "%VITE_METRIKA_COUNTER%";
  ym(window.METRIKA_COUNTER, "init", {
    clickmap: true,
    trackLinks: true,
    accurateTrackBounce: true,
    defer: true
  });
</script>
<noscript>
  <div>
    <img src="https://mc.yandex.ru/watch/%VITE_METRIKA_COUNTER%" style="position:absolute; left:-9999px;" alt="" />
  </div>
</noscript>
<!-- /Yandex.Metrika counter -->
```

### 3.2 Analytics Utility

A dedicated utility for tracking events (`bot/webapp/src/utils/analytics.ts`):

```typescript
// Get client ID for cross-device tracking
export async function getClientId(): Promise<string> {
  const cached = localStorage.getItem("ym_client_id");
  if (cached) return cached;

  return new Promise<string>(resolve => {
    window.ym(getMetrikaCounter(), "getClientID", (id: string) => {
      localStorage.setItem("ym_client_id", id);
      resolve(id);
    });
  });
}

// Track custom events
export function trackEvent(name: string, params?: Record<string, any>): void {
  try {
    window.ym(getMetrikaCounter(), "reachGoal", name, params);
  } catch (error) {
    console.error("Error tracking event:", error);
  }
}
```

### 3.3 API Integration

The client ID is passed to the backend with every API request (`bot/webapp/src/api/client.ts`):

```typescript
// Add interceptor to include the Metrica client ID with every request
apiClient.interceptors.request.use(async config => {
  try {
    const clientId = await getClientId();
    if (clientId) {
      config.headers['X-Client-Id'] = clientId;
    }
  } catch (error) {
    // Silent fail
    console.error('Failed to add client ID to request:', error);
  }
  return config;
});
```

## 4. Backend Implementation

### 4.1 ClientID Middleware

The middleware extracts the client ID from headers or cookies (`web/app/api/v1/middleware.py`):

```python
class ClientIDMiddleware(BaseHTTPMiddleware):
    """Middleware to extract and manage Yandex Metrica client IDs"""
    
    async def dispatch(self, request: Request, call_next):
        # Extract client ID from headers or cookies
        client_id = request.headers.get("X-Client-Id") or request.cookies.get("_ym_uid")
        
        # If not found, generate a new one
        if not client_id:
            client_id = str(uuid.uuid4())
        
        # Store in request state for use in route handlers
        request.state.client_id = client_id
        
        # Process the request
        response = await call_next(request)
        
        # Set the client ID cookie in the response if it wasn't in cookies
        if not request.cookies.get("_ym_uid"):
            response.set_cookie(
                "_ym_uid", 
                client_id, 
                max_age=31536000,  # 1 year
                httponly=False,    # Allow JS to access for Metrica
                samesite="lax"
            )
        
        return response
```

### 4.2 Measurement Protocol Helper

The helper sends server-side events to Yandex Metrica (`web/app/infrastructure/metrika.py`):

```python
async def send_metrika_event(
    client_id: str,
    action: str,
    value: Optional[int] = None,
    **extra: Any
) -> None:
    """
    Send an event to Yandex Metrica using the Measurement Protocol.
    """
    # Skip if httpx not available
    if httpx is None:
        return
        
    # Skip if no counter ID or token is configured
    if not settings.METRIKA_COUNTER or not settings.METRIKA_MP_TOKEN:
        return
        
    # Build parameters
    params: Dict[str, Any] = {
        "tid": settings.METRIKA_COUNTER,
        "cid": client_id,
        "t": "event",
        "ea": action,
        "ms": settings.METRIKA_MP_TOKEN,
        **extra,
    }
    
    # Add value if provided
    if value is not None:
        params["ev"] = value
    
    try:
        # Use httpx for async HTTP requests
        async with httpx.AsyncClient() as client:
            await client.post(
                "https://mc.yandex.ru/collect", 
                params=params, 
                timeout=2.0
            )
    except Exception as e:
        # Silent fail - don't break app functionality if analytics fails
        print(f"Metrika error: {e}")
```

### 4.3 Usage in Services

Example of tracking a booking cancellation:

```python
# Track event in analytics
if client_id:
    track_async_event(
        client_id=client_id,
        action="booking_cancelled",
        value=1,
        ec="booking",
        el=str(booking_id),
        tour_id=str(booking.departure.tour_id),
        amount=str(booking.total_amount),
        time_to_departure=str((booking.departure.starts_at - now).total_seconds() // 3600)
    )
```

## 5. Tracked Events

### 5.1 Frontend Events

| Event Name | Description | When Triggered |
|------------|-------------|----------------|
| `view_tour` | User viewed a tour | Tour detail page loaded |
| `tap_booking_button` | User tapped "Book" button | On booking button click |
| `checkout_complete` | Completed checkout process | After successful checkout |

### 5.2 Backend Events

| Event Name | Description | When Triggered |
|------------|-------------|----------------|
| `booking_created` | Booking was created | After successful DB insert |
| `booking_confirmed` | Booking was confirmed | When agency confirms a booking |
| `booking_rejected` | Booking was rejected | When agency rejects a booking |
| `booking_cancelled` | Booking was cancelled | When user cancels their booking |
| `payment_success` | Payment was successful | After payment webhook confirms |

## 6. Testing & Verification

To verify the integration is working correctly:

1. Open the Yandex Metrica dashboard
2. Check the "Real-time" section to see current visitors
3. Look for goal completions to verify events are being tracked
4. Test backend events by monitoring the "Events" section after triggering server-side actions 