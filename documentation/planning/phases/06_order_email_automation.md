# Phase 7: Order & Email Automation

**Status**: 📋 PENDING
**Dependencies**: Phase 3 (Shopify), Phase 6 (LLM Integration)
**Estimated Duration**: 2-3 weeks

---

## Overview

Send order notifications to Telegram and enable LLM-assisted email responses via Gmail integration.

### Goals

1. Telegram notifications for new orders (real-time)
2. Gmail API integration for reading customer emails
3. LLM-drafted responses with human review
4. Order-aware context for better responses
5. Audit trail for all email interactions

### Workflow

```
Customer Email → Gmail API → Parse Context → LLM Draft
                                               ↓
                            Telegram Notification (with draft)
                                               ↓
                              Admin Review → Approve/Edit/Reject
                                               ↓
                                    Send via Gmail API
```

---

## Sub-Phase Breakdown

### 7.1 Order Notifications
**Duration**: 0.5 weeks

**Deliverables**:
- Telegram notification on new orders
- Order summary formatting
- Product links in notification
- Quick action buttons

### 7.2 Gmail Integration
**Duration**: 1 week

**Deliverables**:
- GmailService with OAuth
- Inbox monitoring (polling or push)
- Email parsing and context extraction
- Thread management

### 7.3 Email Orchestration
**Duration**: 1 week

**Deliverables**:
- EmailOrchestrationService
- LLM draft generation
- Telegram review workflow
- Send with approval

---

## Data Model

### EmailThread

```sql
CREATE TABLE IF NOT EXISTS email_threads (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    -- Gmail identifiers
    gmail_thread_id TEXT NOT NULL UNIQUE,
    gmail_message_ids TEXT[],  -- All message IDs in thread

    -- Context
    customer_email TEXT NOT NULL,
    customer_name TEXT,
    subject TEXT NOT NULL,

    -- Order linkage
    shopify_order_id BIGINT,
    detected_order_numbers TEXT[],  -- Mentioned in email body

    -- Status
    status VARCHAR(30) DEFAULT 'new',
        -- 'new', 'draft_pending', 'awaiting_review', 'sent', 'closed'
    priority VARCHAR(20) DEFAULT 'normal',  -- 'low', 'normal', 'high', 'urgent'

    -- Classification
    category VARCHAR(50),  -- 'inquiry', 'complaint', 'return', 'shipping', 'other'
    sentiment VARCHAR(20),  -- 'positive', 'neutral', 'negative'

    -- Timestamps
    first_email_at TIMESTAMP NOT NULL,
    last_email_at TIMESTAMP NOT NULL,
    responded_at TIMESTAMP,

    -- Assignee
    assigned_to_user_id UUID REFERENCES users(id),
    assigned_at TIMESTAMP,

    -- Metadata
    custom_metadata JSONB,

    -- Audit
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_email_threads_gmail ON email_threads(gmail_thread_id);
CREATE INDEX idx_email_threads_customer ON email_threads(customer_email);
CREATE INDEX idx_email_threads_order ON email_threads(shopify_order_id);
CREATE INDEX idx_email_threads_status ON email_threads(status);
```

### EmailMessage

```sql
CREATE TABLE IF NOT EXISTS email_messages (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    -- Thread reference
    thread_id UUID NOT NULL REFERENCES email_threads(id),

    -- Gmail identifiers
    gmail_message_id TEXT NOT NULL UNIQUE,

    -- Direction
    direction VARCHAR(10) NOT NULL,  -- 'inbound' or 'outbound'

    -- Content
    from_email TEXT NOT NULL,
    to_email TEXT NOT NULL,
    subject TEXT,
    body_text TEXT,
    body_html TEXT,

    -- For outbound: approval workflow
    llm_draft TEXT,
    llm_conversation_id UUID REFERENCES llm_conversations(id),
    approved_text TEXT,  -- Final sent version (may differ from draft)
    approved_by_user_id UUID REFERENCES users(id),
    approved_at TIMESTAMP,

    -- Timestamps
    gmail_date TIMESTAMP NOT NULL,
    sent_at TIMESTAMP,

    -- Audit
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_email_messages_thread ON email_messages(thread_id);
CREATE INDEX idx_email_messages_gmail ON email_messages(gmail_message_id);
CREATE INDEX idx_email_messages_direction ON email_messages(direction);
```

---

## Service Interfaces

### OrderNotificationService

```python
# src/services/notifications/order_notification_service.py

class OrderNotificationService(BaseService):
    """
    Send order notifications to Telegram.
    """

    def __init__(self):
        super().__init__()
        self.telegram_service = TelegramService()
        self.shopify_repo = ShopifyOrderRepository()
        self.product_repo = ShopifyProductRepository()

    async def notify_new_order(self, shopify_order_id: int) -> bool:
        """
        Send Telegram notification for new order.

        Format:
        🛒 New Order #1234
        ━━━━━━━━━━━━━━━━
        Items:
        • Blue Hoodie (L) x1 - $49.99
        • Black T-Shirt (M) x2 - $29.99

        Total: $109.97
        Status: Paid ✅

        [View in Shopify] [View Products]
        """
        pass

    async def notify_order_status_change(
        self,
        shopify_order_id: int,
        old_status: str,
        new_status: str,
    ) -> bool:
        """Notify on fulfillment status changes."""
        pass

    def format_order_notification(self, order: ShopifyOrder) -> str:
        """Format order data for Telegram."""
        pass
```

### GmailService

```python
# src/services/integrations/gmail_service.py

from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials

class GmailService(BaseService):
    """
    Gmail API integration for email management.
    """

    def __init__(self):
        super().__init__()
        self.thread_repo = EmailThreadRepository()
        self.message_repo = EmailMessageRepository()
        self.credentials = self._load_credentials()

    # ─────────────────────────────────────────────────────────────
    # Inbox Monitoring
    # ─────────────────────────────────────────────────────────────

    async def check_inbox(
        self,
        label: str = "INBOX",
        max_results: int = 50,
    ) -> List[dict]:
        """
        Check for new emails.

        Returns list of new threads not yet in our database.
        """
        pass

    async def get_thread(self, gmail_thread_id: str) -> dict:
        """Get full thread with all messages."""
        pass

    async def get_message(self, gmail_message_id: str) -> dict:
        """Get single message details."""
        pass

    # ─────────────────────────────────────────────────────────────
    # Sending
    # ─────────────────────────────────────────────────────────────

    async def send_reply(
        self,
        thread_id: str,  # Our internal thread ID
        body: str,
        subject: Optional[str] = None,
    ) -> dict:
        """
        Send reply to a thread.

        Returns:
            {
                "success": True,
                "gmail_message_id": "...",
                "sent_at": datetime,
            }
        """
        pass

    async def create_draft(
        self,
        thread_id: str,
        body: str,
        subject: Optional[str] = None,
    ) -> dict:
        """Create Gmail draft (for preview before send)."""
        pass

    # ─────────────────────────────────────────────────────────────
    # Parsing
    # ─────────────────────────────────────────────────────────────

    def extract_order_numbers(self, email_body: str) -> List[str]:
        """Extract order numbers mentioned in email."""
        pass

    def classify_email(self, subject: str, body: str) -> dict:
        """
        Classify email type and sentiment.

        Returns:
            {
                "category": "shipping",
                "sentiment": "neutral",
                "priority": "normal",
            }
        """
        pass
```

### EmailOrchestrationService

```python
# src/services/notifications/email_orchestration_service.py

class EmailOrchestrationService(BaseService):
    """
    Orchestrate the email response workflow:
    1. Receive email
    2. Generate LLM draft
    3. Send to Telegram for review
    4. Handle approval/rejection
    5. Send response
    """

    def __init__(self):
        super().__init__()
        self.gmail_service = GmailService()
        self.llm_service = LLMService()
        self.telegram_service = TelegramService()
        self.thread_repo = EmailThreadRepository()

    async def process_new_email(self, gmail_thread_id: str) -> dict:
        """
        Process a new incoming email.

        Steps:
        1. Fetch thread from Gmail
        2. Create/update thread in DB
        3. Link to Shopify order if found
        4. Classify email
        5. Generate LLM draft
        6. Send to Telegram for review
        """
        pass

    async def handle_approval(
        self,
        thread_id: str,
        approved_text: str,
        user_id: str,
    ) -> dict:
        """
        Handle admin approval of email draft.

        Sends the email via Gmail.
        """
        pass

    async def handle_rejection(
        self,
        thread_id: str,
        reason: str,
        user_id: str,
    ) -> dict:
        """
        Handle rejection of email draft.

        Options:
        - Regenerate draft
        - Mark for manual handling
        - Close thread
        """
        pass

    async def send_review_to_telegram(
        self,
        thread: EmailThread,
        draft: str,
    ) -> bool:
        """
        Send email draft to Telegram for review.

        Format:
        📧 Email Response Needed
        ━━━━━━━━━━━━━━━━━━━━━━━
        From: customer@email.com
        Order: #1234
        Category: Shipping Inquiry

        Customer said:
        "Where is my order? It's been 5 days..."

        Draft Response:
        "Thank you for reaching out! I can see your
        order #1234 is currently in transit..."

        [✅ Approve] [✏️ Edit] [🔄 Regenerate] [❌ Close]
        """
        pass
```

---

## Telegram Commands & Callbacks

```python
# New handlers in TelegramService

async def _handle_email_approve(self, query, thread_id: str):
    """Approve and send email draft."""
    pass

async def _handle_email_edit(self, query, thread_id: str):
    """Open edit mode for draft."""
    pass

async def _handle_email_regenerate(self, query, thread_id: str):
    """Generate new draft with different prompt."""
    pass

async def _handle_email_close(self, query, thread_id: str):
    """Close thread without responding."""
    pass

async def _handle_emails(self, update, context):
    """
    /emails - List pending email responses

    Shows:
    - Threads awaiting response
    - Draft status
    - Priority
    """
    pass
```

---

## Configuration

```python
# settings.py additions

class Settings(BaseSettings):
    # Phase 7: Email Automation
    ENABLE_EMAIL_AUTOMATION: bool = False

    # Gmail OAuth
    GMAIL_CLIENT_ID: Optional[str] = None
    GMAIL_CLIENT_SECRET: Optional[str] = None
    GMAIL_REFRESH_TOKEN: Optional[str] = None
    GMAIL_SEND_AS_EMAIL: Optional[str] = None  # The "from" address

    # Polling
    GMAIL_CHECK_INTERVAL_SECONDS: int = 60
    GMAIL_LABELS_TO_MONITOR: List[str] = ["INBOX"]

    # Order notifications
    ENABLE_ORDER_NOTIFICATIONS: bool = True
    ORDER_NOTIFICATION_CHAT_ID: Optional[int] = None  # Specific chat for orders
```

---

## Implementation Checklist

### 7.1 Order Notifications
- [ ] Create `src/services/notifications/order_notification_service.py`
- [ ] Implement order formatting
- [ ] Add webhook handler for Shopify orders
- [ ] Add Telegram notification with buttons
- [ ] Test notification delivery

### 7.2 Gmail Integration
- [ ] Create `email_threads` table
- [ ] Create `email_messages` table
- [ ] Create `src/services/integrations/gmail_service.py`
- [ ] Implement OAuth flow
- [ ] Implement inbox monitoring
- [ ] Implement send/reply

### 7.3 Email Orchestration
- [ ] Create `src/services/notifications/email_orchestration_service.py`
- [ ] Integrate with LLMService for drafts
- [ ] Implement Telegram review workflow
- [ ] Add approval/rejection handlers
- [ ] Add `/emails` command
- [ ] Write tests

---

## Success Metrics

- **Order notification latency**: < 30 seconds from order
- **Email response time**: Avg time from receipt to send
- **Draft acceptance rate**: % sent as-is vs edited
- **Customer satisfaction**: Track reply quality
