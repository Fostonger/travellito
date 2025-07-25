# Travellito

## Telegram WebApp Authentication Flow

### Overview

The Telegram WebApp authentication flow uses the official Telegram WebApp `initData` to securely authenticate users. This flow:

1. Verifies the HMAC signature of `initData` against the bot token
2. Issues HttpOnly, Secure, SameSite=None cookies for authentication
3. Tracks user referrals and maintains an audit trail
4. Provides automatic token refresh

### Architecture

```
┌─────────────────┐     ┌───────────────┐     ┌───────────────────┐
│ Telegram WebApp │────▶│ /auth/telegram│────▶│ Verify initData   │
│ (React)         │     │ /init         │     │ HMAC signature    │
└─────────────────┘     └───────────────┘     └───────────────────┘
        │                                               │
        │                                               ▼
┌─────────────────┐                         ┌───────────────────┐
│ API Requests    │◀────────────────────────│ Set HttpOnly      │
│ with Cookies    │                         │ Secure Cookies    │
└─────────────────┘                         └───────────────────┘
        │                                               ▲
        ▼                                               │
┌─────────────────┐     ┌───────────────┐     ┌───────────────────┐
│ 401 Unauthorized│────▶│ /auth/refresh │────▶│ Issue new         │
│                 │     │               │     │ access token      │
└─────────────────┘     └───────────────┘     └───────────────────┘
```

### Environment Variables

```
# Telegram Bot configuration
BOT_TOKEN=123456789:ABCDEFGHIJKLMNOPQRSTUVWXYZ  # Get from @BotFather
ALLOWED_AUTH_SKEW_SECONDS=86400  # 24 hours in seconds

# JWT configuration
SECRET_KEY=your-secure-secret-key-at-least-32-chars
JWT_ACCESS_TTL=900  # 15 minutes in seconds
JWT_REFRESH_TTL=1209600  # 14 days in seconds

# Cookie configuration
COOKIE_DOMAIN=.example.com  # Domain for cookies (include subdomain)
COOKIE_SECURE=true  # Set to false for local development without HTTPS
```

### API Endpoints

#### POST /auth/telegram/init

Authenticates a user with Telegram WebApp initData.

**Request:**
```json
{
  "init_data": "query_id=AAHdF6IQAAAAAN0XohDhrOrc&user=%7B%22id%22%3A123456789%2C%22first_name%22%3A%22John%22%2C%22last_name%22%3A%22Doe%22%2C%22username%22%3A%22johndoe%22%2C%22language_code%22%3A%22en%22%7D&auth_date=1625097433&hash=abc123def456..."
}
```

**Response:**
```json
{
  "user": {
    "id": 42,
    "role": "bot_user",
    "first": "John",
    "last": "Doe"
  }
}
```

**Cookies Set:**
- `access_token`: Short-lived JWT (15 minutes)
- `refresh_token`: Long-lived JWT (14 days)

#### POST /auth/refresh

Refreshes an access token using the refresh token cookie.

**Request:** No body needed (uses cookies)

**Response:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

**Cookies Set:**
- `access_token`: New short-lived JWT (15 minutes)

#### POST /auth/logout

Logs out the user by clearing auth cookies.

**Request:** No body needed

**Response:**
```json
{
  "success": true
}
```

### Frontend Integration

1. Include the Telegram WebApp script:
```html
<script src="https://telegram.org/js/telegram-web-app.js"></script>
```

2. Signal readiness to Telegram:
```js
if (window.Telegram?.WebApp?.ready) {
  window.Telegram.WebApp.ready();
}
```

3. Get initData and authenticate:
```js
const tg = window.Telegram?.WebApp;
if (tg && tg.initData) {
  await axios.post('/api/v1/auth/telegram/init', { 
    init_data: tg.initData 
  }, { withCredentials: true });
}
```

4. Configure axios for cookies:
```js
axios.defaults.withCredentials = true;
```

### Security Considerations

1. **Signature Verification**: The backend verifies the HMAC signature of `initData` using SHA-256 with the bot token.
2. **Timestamp Validation**: Auth requests with stale timestamps (>24h) are rejected.
3. **HttpOnly Cookies**: Tokens are stored in HttpOnly cookies to prevent JavaScript access.
4. **Secure Cookies**: Cookies are marked Secure to ensure HTTPS-only transmission.
5. **SameSite=None**: Required for cookies in embedded iframes (like Telegram WebApp).

### Migration Guide

To migrate from the old URL/localStorage token approach:

1. Update frontend to use the new authentication flow
2. Deploy backend changes
3. Users will automatically re-authenticate on next visit
4. Old localStorage tokens will be ignored

### Testing with curl

```bash
# Authenticate with initData
curl -X POST https://api.example.com/api/v1/auth/telegram/init \
  -H "Content-Type: application/json" \
  -d '{"init_data":"query_id=AAHdF6IQAAAAAN0XohDhrOrc&user=%7B%22id%22%3A123456789%2C%22first_name%22%3A%22John%22%7D&auth_date=1625097433&hash=abc123def456..."}' \
  -c cookies.txt

# Make authenticated request
curl https://api.example.com/api/v1/auth/me \
  -b cookies.txt

# Refresh token
curl -X POST https://api.example.com/api/v1/auth/refresh \
  -b cookies.txt \
  -c cookies.txt

# Logout
curl -X POST https://api.example.com/api/v1/auth/logout \
  -b cookies.txt
```