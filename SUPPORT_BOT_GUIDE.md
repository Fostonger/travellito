# Travellito Support Bot System Guide

## Overview

The Travellito Support Bot is a comprehensive customer support system that handles:
- Tourist questions and issues
- Landlord commission payment requests
- Admin notification and response system

## System Components

### 1. Support Bot (Telegram Bot)
- **Purpose**: Interface for tourists to report issues and ask questions
- **Bot Username**: Set via `SUPPORT_BOT_TOKEN` environment variable
- **Features**:
  - Question submission
  - Issue reporting
  - Automatic admin notification

### 2. Landlord Payment System
- **Purpose**: Allow landlords to request commission payments
- **Requirements**:
  - Minimum 10 unique engaged users
  - Completed payment information (phone number, bank name)
  - Available balance > 0
- **Features**:
  - Balance tracking
  - Payment request submission
  - Payment status tracking

### 3. Admin Notification System
- **Purpose**: Notify admins of support requests and payment requests
- **Features**:
  - Real-time Telegram notifications
  - Reply functionality for support messages
  - One-click payment processing

## Database Schema

### New Tables

1. **support_messages**
   - Stores all support requests from users
   - Types: issue, question, payment_request
   - Status tracking: pending, in_progress, resolved

2. **support_responses**
   - Admin responses to support messages
   - Links to support_messages

3. **landlord_payment_requests**
   - Payment requests from landlords
   - Tracks amount, status, and processing details

4. **landlord_payment_history**
   - Historical record of all payments made

## Setup Instructions

### 1. Environment Variables

Add to your `.env` file:
```env
# Support Bot Token from BotFather
SUPPORT_BOT_TOKEN=your_support_bot_token_here

# Webhook URL for Support Bot (optional, for production)
SUPPORT_BOT_WEBHOOK_URL=https://yourdomain.com
```

### 2. Database Migration

Run the migration to create new tables:
```bash
docker-compose exec web alembic upgrade head
```

### 3. Docker Compose

The support bot is included in docker-compose.yml:
```yaml
support-bot:
  build:
    context: ./bot
    dockerfile: Dockerfile.support
  environment:
    SUPPORT_BOT_TOKEN: "${SUPPORT_BOT_TOKEN}"
    SUPPORT_BOT_WEBHOOK_URL: "${SUPPORT_BOT_WEBHOOK_URL}"
    WEB_API: "http://web:8000"
  depends_on: [web]
  ports: ["8081:8001"]
  restart: unless-stopped
```

### 4. Start the System

```bash
docker-compose up -d support-bot
```

## Usage Guide

### For Tourists

1. Start conversation with support bot
2. Choose "Ask Question" or "Report Issue"
3. Type your message
4. Receive confirmation and ticket number
5. Get notified when admin responds

### For Landlords

1. Navigate to dashboard at `/api/v1/landlord`
2. View available balance in header and dashboard
3. Click "Получить комиссионные" when eligible
4. Confirm payment request
5. Track status on dashboard

### For Admins

1. Receive notifications in Telegram for:
   - New support messages
   - Payment requests
2. Reply to support messages using: `/reply <message_id> <your response>`
3. Process payments by clicking "✅ Обработать выплату" button

## API Endpoints

### Support Endpoints

- `POST /api/v1/support/messages` - Create support message
- `GET /api/v1/support/messages` - List messages (admin only)
- `GET /api/v1/support/messages/{id}` - Get specific message
- `POST /api/v1/support/messages/{id}/respond` - Admin response

### Landlord Payment Endpoints

- `GET /api/v1/landlord/payment/status` - Check payment eligibility
- `POST /api/v1/landlord/payment/request` - Request payment

### Internal Endpoints

- `GET /api/v1/support/internal/admin-telegram-ids` - Get admin Telegram IDs
- `POST /api/v1/support/payment-requests/{id}/process` - Process payment

## Security Considerations

1. **Authentication**: All endpoints require authentication
2. **Authorization**: 
   - Admins can view all messages and process payments
   - Users can only view their own messages
   - Landlords can only request payments for their own accounts
3. **Payment Verification**: 
   - Automatic validation of requirements
   - Admin approval required for all payments

## Troubleshooting

### Common Issues

1. **Bot not responding**
   - Check `SUPPORT_BOT_TOKEN` is set correctly
   - Verify bot is running: `docker-compose logs support-bot`

2. **Admins not receiving notifications**
   - Ensure admin users have `tg_id` set in database
   - Check admin role is correctly set to "admin"

3. **Payment button disabled**
   - Check all requirements in tooltip
   - Verify payment information is complete in profile

### Logs

View support bot logs:
```bash
docker-compose logs -f support-bot
```

View web service logs for payment processing:
```bash
docker-compose logs -f web | grep -i payment
```

## Future Enhancements

1. **Multi-language Support**: Add language detection and responses
2. **Auto-assignment**: Automatically assign support tickets to available admins
3. **SLA Tracking**: Monitor response times and set alerts
4. **Payment Reports**: Generate monthly payment reports for accounting
5. **FAQ Bot**: Add automated responses for common questions 