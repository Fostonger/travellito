# Migrate Telegram auth to secure initData flow (cookies, JWT rotation, referral overwrite)

## Executive Summary

This PR implements a secure Telegram WebApp authentication flow using the official `initData` verification mechanism. Key improvements:

1. **Security**: Replaces insecure URL tokens with HttpOnly cookies and proper HMAC verification
2. **Reliability**: Adds graceful fallback for non-Telegram environments
3. **Referral Tracking**: Implements consistent referral overwriting and audit trail
4. **DevEx**: Provides comprehensive documentation and testing tools

## Flow Diagram

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

## Security Checklist

- [x] **HMAC Verification**: Properly implemented with constant-time comparison
- [x] **Timestamp Validation**: Rejects stale auth_date values (configurable, default 24h)
- [x] **HttpOnly Cookies**: Prevents JavaScript access to tokens
- [x] **Secure Cookies**: Ensures HTTPS-only transmission
- [x] **SameSite=None**: Required for cookies in embedded iframes (like Telegram WebApp)
- [x] **Token Rotation**: Short-lived access tokens (15 min) with refresh mechanism
- [x] **No URL/LocalStorage**: Removed all insecure token storage
- [x] **Structured Logging**: Added for auth events and referral changes

## Migration Plan

### Backend Changes

1. Added `verify_telegram_webapp_data` helper to validate `initData` HMAC
2. Implemented `/auth/telegram/init` endpoint for WebApp authentication
3. Enhanced `/auth/refresh` to work with cookies
4. Updated `/auth/logout` to clear all cookies
5. Added `referral_events` table for audit trail
6. Updated security middleware to check cookies

### Frontend Changes

1. Added Telegram WebApp script and initialization
2. Implemented `TelegramFallback` component for graceful degradation
3. Updated authentication flow to use `initData` and cookies
4. Configured axios for cookie-based auth
5. Removed all localStorage token handling

### How to Invalidate Legacy Tokens

1. Legacy tokens will naturally expire based on their TTL
2. Users will automatically re-authenticate on next visit
3. No manual intervention required

## Backward Compatibility & Re-login

- The new system is backward compatible with existing users
- Users will be prompted to re-authenticate on their next visit
- The transition is seamless - no user action required beyond standard Telegram authentication

## Known Limitations & Next Steps

1. **Cross-Origin Limitations**: SameSite=None cookies require HTTPS
2. **Token Revocation**: Currently no explicit token revocation (future enhancement)
3. **Rate Limiting**: Should be added to prevent abuse

## Testing

1. Verified HMAC signature validation with sample `initData`
2. Tested referral overwrite and audit trail
3. Confirmed cookie-based auth flow works in Telegram WebApp
4. Validated graceful fallback in non-Telegram environments 