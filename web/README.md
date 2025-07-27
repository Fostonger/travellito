# Token Refresh Implementation

This document describes the token refresh implementation in the Travellito application.

## Overview

The application uses JWT tokens for authentication with two types of tokens:
- **Access Token**: Short-lived token (15 minutes) used for API access
- **Refresh Token**: Long-lived token (30 days) used to obtain new access tokens

Authentication can be done in two ways:
1. **Cookie-based**: Tokens stored in HTTP-only cookies
2. **Bearer token**: Tokens stored in localStorage and sent via Authorization header

## Implementation Details

### Server-side Components

1. **TokenRefreshMiddleware** (`web/app/api/v1/middleware.py`)
   - Automatically refreshes expired access tokens using refresh tokens
   - Intercepts requests before they reach the handlers
   - Sets the new access token as a cookie in the response

2. **Auth Endpoints** (`web/app/api/v1/endpoints/auth.py`)
   - `/api/v1/auth/login`: Issues access and refresh tokens, sets them as cookies
   - `/api/v1/auth/refresh`: Refreshes access token using refresh token from cookie or request body
   - `/api/v1/auth/logout`: Clears auth cookies

3. **Auth Service** (`web/app/services/auth_service.py`)
   - `refresh_access_token()`: Validates refresh token and issues new access token
   - Verifies user still exists and has the same role before refreshing

4. **Security Module** (`web/app/security.py`)
   - `_extract_token()`: Extracts token from Authorization header or cookie
   - `_extract_refresh_token()`: Extracts refresh token from cookie
   - `decode_token()`: Verifies and decodes JWT token
   - `create_token()`: Creates new JWT tokens

### Client-side Components

1. **Auth.js** (`web/static/auth.js`)
   - Manages token storage in localStorage
   - Provides fetch interceptor for automatic token refresh
   - Handles both cookie-based and bearer token authentication
   - Detects token expiration and triggers refresh

2. **Token Refresh Test Page** (`web/templates/token_refresh_test.html`)
   - Test interface for token refresh functionality
   - Shows token status and allows testing different auth scenarios

## How It Works

1. When a user logs in, both access and refresh tokens are issued
   - Tokens are stored in HTTP-only cookies for browser security
   - Tokens are also returned in the response body for API clients

2. For each request:
   - Client-side: The fetch interceptor checks if the token is expired and refreshes it if needed
   - Server-side: The middleware checks if the token is expired and refreshes it if needed

3. When the access token expires:
   - The server returns a 401 Unauthorized response
   - The client uses the refresh token to get a new access token
   - The request is retried with the new access token

4. If the refresh token is invalid or expired:
   - User is redirected to the login page

## Testing

Use the token refresh test page at `/token-refresh-test` to test the token refresh functionality:
- View current token status
- Test API calls with expired tokens
- Test cookie-based authentication
- Simulate token expiration

## Security Considerations

- Refresh tokens are stored in HTTP-only cookies to prevent XSS attacks
- Tokens are validated on each refresh to ensure user still exists and has the same role
- Tokens include minimal claims to reduce exposure
- Short-lived access tokens limit the window of opportunity for token theft 