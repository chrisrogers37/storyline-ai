# Phase 6: LLM Integration

**Status**: 📋 PENDING
**Dependencies**: Phase 5 (Media-Product Linking)
**Estimated Duration**: 3-4 weeks

---

## Overview

Add AI capabilities for content suggestions, automated responses, and optimization insights using Claude or OpenAI APIs.

### Goals

1. Abstract LLM provider (Claude/OpenAI interchangeable)
2. Content suggestion engine (what to post, when, which products)
3. Email response drafting (customer service automation)
4. Prompt management system (version-controlled, auditable)
5. Usage tracking and cost management

### Non-Goals (This Phase)

- Image generation (future)
- Video generation (future)
- Autonomous actions (always human-in-the-loop)

---

## Sub-Phase Breakdown

### 6.1 LLM Service Abstraction
**Duration**: 1 week

**Deliverables**:
- LLMService with provider abstraction
- Claude and OpenAI implementations
- Token/cost tracking
- Rate limiting

### 6.2 Prompt Management
**Duration**: 0.5 weeks

**Deliverables**:
- Prompt templates table
- Version control for prompts
- Variable substitution
- A/B testing support

### 6.3 Content Suggestions
**Duration**: 1 week

**Deliverables**:
- Posting suggestion engine
- Product recommendation based on trends
- Caption generation
- Hashtag suggestions

### 6.4 Email Draft Generation
**Duration**: 1 week

**Deliverables**:
- Email context analysis
- Response draft generation
- Tone/style customization
- Human review workflow

---

## Data Model

### PromptTemplate

```sql
CREATE TABLE IF NOT EXISTS prompt_templates (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    -- Identification
    name VARCHAR(100) NOT NULL UNIQUE,
    category VARCHAR(50) NOT NULL,  -- 'content', 'email', 'analysis'

    -- Template content
    system_prompt TEXT,
    user_prompt_template TEXT NOT NULL,  -- With {{variables}}
    required_variables TEXT[],  -- ['product_name', 'customer_name']

    -- Configuration
    model VARCHAR(50) DEFAULT 'claude-3-sonnet',
    temperature NUMERIC(2, 1) DEFAULT 0.7,
    max_tokens INTEGER DEFAULT 1000,

    -- Versioning
    version INTEGER DEFAULT 1,
    is_active BOOLEAN DEFAULT TRUE,
    parent_version_id UUID REFERENCES prompt_templates(id),

    -- A/B testing
    variant_name VARCHAR(50),  -- 'control', 'variant_a', etc.
    traffic_percentage INTEGER DEFAULT 100,

    -- Audit
    created_by_user_id UUID REFERENCES users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_prompt_templates_name ON prompt_templates(name);
CREATE INDEX idx_prompt_templates_category ON prompt_templates(category);
CREATE INDEX idx_prompt_templates_active ON prompt_templates(is_active) WHERE is_active = TRUE;
```

### LLMConversation

```sql
CREATE TABLE IF NOT EXISTS llm_conversations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    -- Context
    conversation_type VARCHAR(50) NOT NULL,  -- 'email_draft', 'suggestion', 'analysis'
    reference_type VARCHAR(50),  -- 'order', 'media', 'product'
    reference_id TEXT,           -- ID of related entity

    -- Messages (JSONB array for flexibility)
    messages JSONB NOT NULL,  -- [{role, content, timestamp}, ...]

    -- Prompt used
    prompt_template_id UUID REFERENCES prompt_templates(id),

    -- Result
    final_output TEXT,
    was_accepted BOOLEAN,  -- Did user accept/use the output?
    user_feedback TEXT,

    -- Cost tracking
    input_tokens INTEGER,
    output_tokens INTEGER,
    estimated_cost NUMERIC(10, 6),  -- In USD
    model_used VARCHAR(50),

    -- Audit
    initiated_by_user_id UUID REFERENCES users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP
);

CREATE INDEX idx_llm_conversations_type ON llm_conversations(conversation_type);
CREATE INDEX idx_llm_conversations_reference ON llm_conversations(reference_type, reference_id);
CREATE INDEX idx_llm_conversations_user ON llm_conversations(initiated_by_user_id);
```

### GeneratedContent

```sql
CREATE TABLE IF NOT EXISTS generated_content (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    -- Type
    content_type VARCHAR(50) NOT NULL,  -- 'caption', 'email', 'hashtags', 'suggestion'

    -- The content
    content TEXT NOT NULL,
    structured_content JSONB,  -- For complex outputs

    -- Source
    conversation_id UUID REFERENCES llm_conversations(id),
    prompt_template_id UUID REFERENCES prompt_templates(id),

    -- Context
    media_item_id UUID REFERENCES media_items(id),
    shopify_product_id BIGINT,
    shopify_order_id BIGINT,

    -- Status
    status VARCHAR(20) DEFAULT 'draft',  -- 'draft', 'approved', 'rejected', 'used'
    approved_by_user_id UUID REFERENCES users(id),
    approved_at TIMESTAMP,

    -- Audit
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_generated_content_type ON generated_content(content_type);
CREATE INDEX idx_generated_content_status ON generated_content(status);
CREATE INDEX idx_generated_content_media ON generated_content(media_item_id);
```

---

## Service Interface

### LLMService (Abstraction)

```python
# src/services/domain/llm_service.py

from abc import ABC, abstractmethod

class LLMProvider(ABC):
    """Abstract LLM provider interface."""

    @abstractmethod
    async def complete(
        self,
        messages: List[dict],
        model: str,
        temperature: float,
        max_tokens: int,
    ) -> dict:
        """Generate completion from messages."""
        pass

    @abstractmethod
    def estimate_cost(self, input_tokens: int, output_tokens: int, model: str) -> float:
        """Estimate cost in USD."""
        pass


class ClaudeProvider(LLMProvider):
    """Anthropic Claude implementation."""
    pass


class OpenAIProvider(LLMProvider):
    """OpenAI GPT implementation."""
    pass


class LLMService(BaseService):
    """
    Main LLM service - handles all AI operations.
    """

    def __init__(self, provider: str = "claude"):
        super().__init__()
        self.provider = self._get_provider(provider)
        self.prompt_repo = PromptTemplateRepository()
        self.conversation_repo = LLMConversationRepository()
        self.content_repo = GeneratedContentRepository()

    # ─────────────────────────────────────────────────────────────
    # Core Operations
    # ─────────────────────────────────────────────────────────────

    async def generate(
        self,
        prompt_name: str,
        variables: dict,
        user_id: Optional[str] = None,
    ) -> dict:
        """
        Generate content using a named prompt template.

        Args:
            prompt_name: Name of prompt template
            variables: Variables to substitute in template
            user_id: User initiating the request

        Returns:
            {
                "success": True,
                "content": "Generated text...",
                "conversation_id": "...",
                "tokens_used": {"input": 100, "output": 50},
                "estimated_cost": 0.0015,
            }
        """
        pass

    async def chat(
        self,
        conversation_id: str,
        user_message: str,
    ) -> dict:
        """Continue an existing conversation."""
        pass

    # ─────────────────────────────────────────────────────────────
    # Content Suggestions
    # ─────────────────────────────────────────────────────────────

    async def suggest_next_post(
        self,
        context: dict,  # recent_posts, trending_products, etc.
    ) -> dict:
        """
        Suggest what to post next.

        Returns:
            {
                "suggestion": "Post the blue hoodie meme...",
                "reasoning": "This product is trending and...",
                "recommended_time": "2026-01-12 14:00",
                "recommended_products": [...],
                "hashtag_suggestions": [...],
            }
        """
        pass

    async def generate_caption(
        self,
        media_id: str,
        product_ids: Optional[List[str]] = None,
        style: str = "casual",  # 'casual', 'professional', 'funny'
    ) -> dict:
        """Generate Instagram caption for media."""
        pass

    async def suggest_hashtags(
        self,
        media_id: str,
        product_ids: Optional[List[str]] = None,
        max_hashtags: int = 30,
    ) -> List[str]:
        """Suggest relevant hashtags."""
        pass

    # ─────────────────────────────────────────────────────────────
    # Email Drafting
    # ─────────────────────────────────────────────────────────────

    async def draft_email_response(
        self,
        order_id: str,
        customer_email: str,
        email_subject: str,
        email_body: str,
        response_type: str = "inquiry",  # 'inquiry', 'complaint', 'return'
    ) -> dict:
        """
        Draft a response to a customer email.

        Returns:
            {
                "draft": "Dear Customer, Thank you for...",
                "tone": "professional",
                "confidence": 0.85,
                "needs_review": True,
                "suggested_actions": ["offer_discount", "expedite_shipping"],
            }
        """
        pass

    # ─────────────────────────────────────────────────────────────
    # Analysis
    # ─────────────────────────────────────────────────────────────

    async def analyze_performance(
        self,
        date_range: tuple,
    ) -> dict:
        """
        AI analysis of posting and sales performance.

        Returns natural language insights and recommendations.
        """
        pass
```

---

## Prompt Templates (Examples)

```yaml
# prompts/content_suggestion.yaml
name: content_suggestion
category: content
system_prompt: |
  You are a social media strategist for an e-commerce brand.
  Your goal is to maximize engagement and sales through strategic posting.

user_prompt_template: |
  Based on the following data, suggest what to post next:

  Recent Posts (last 7 days):
  {{recent_posts}}

  Top Performing Products (by sales):
  {{top_products}}

  Trending Categories:
  {{trending_categories}}

  Current Queue:
  {{current_queue}}

  Today's date: {{current_date}}
  Day of week: {{day_of_week}}

  Provide a specific recommendation including:
  1. Which media to post (or create)
  2. Which products to feature
  3. Optimal posting time
  4. Caption style/tone
  5. Reasoning for your recommendation

required_variables:
  - recent_posts
  - top_products
  - trending_categories
  - current_queue
  - current_date
  - day_of_week
```

```yaml
# prompts/email_response.yaml
name: email_response_inquiry
category: email
system_prompt: |
  You are a helpful customer service representative for an e-commerce store.
  Be friendly, professional, and solution-oriented.
  Never make promises you can't keep (like specific delivery dates).

user_prompt_template: |
  Customer Order: #{{order_number}}
  Order Status: {{order_status}}
  Order Items: {{order_items}}

  Customer Email Subject: {{email_subject}}
  Customer Email Body:
  {{email_body}}

  Draft a response that:
  1. Acknowledges their inquiry
  2. Addresses their specific concern
  3. Provides helpful information
  4. Offers next steps if needed
  5. Maintains a friendly, professional tone

required_variables:
  - order_number
  - order_status
  - order_items
  - email_subject
  - email_body
```

---

## Configuration

```python
# settings.py additions

class Settings(BaseSettings):
    # Phase 6: LLM
    ENABLE_LLM_FEATURES: bool = False
    LLM_PROVIDER: str = "claude"  # 'claude' or 'openai'

    # Claude (Anthropic)
    ANTHROPIC_API_KEY: Optional[str] = None
    CLAUDE_MODEL: str = "claude-3-sonnet-20240229"

    # OpenAI
    OPENAI_API_KEY: Optional[str] = None
    OPENAI_MODEL: str = "gpt-4-turbo-preview"

    # Cost controls
    LLM_DAILY_BUDGET_USD: float = 10.0
    LLM_MAX_TOKENS_PER_REQUEST: int = 4000
    LLM_CACHE_TTL_HOURS: int = 24  # Cache similar requests
```

---

## Implementation Checklist

### 6.1 LLM Service Abstraction
- [ ] Create `src/services/domain/llm_service.py`
- [ ] Implement ClaudeProvider
- [ ] Implement OpenAIProvider
- [ ] Add token/cost tracking
- [ ] Add rate limiting

### 6.2 Prompt Management
- [ ] Create `prompt_templates` table
- [ ] Create `llm_conversations` table
- [ ] Create `generated_content` table
- [ ] Implement PromptTemplateRepository
- [ ] Add variable substitution
- [ ] Add A/B testing support

### 6.3 Content Suggestions
- [ ] Implement `suggest_next_post()`
- [ ] Implement `generate_caption()`
- [ ] Implement `suggest_hashtags()`
- [ ] Create prompt templates
- [ ] Add Telegram `/suggest` command

### 6.4 Email Draft Generation
- [ ] Implement `draft_email_response()`
- [ ] Create email prompt templates
- [ ] Add review workflow
- [ ] Integrate with Order Notifications (Phase 7)

---

## Success Metrics

- **Suggestion acceptance**: % of suggestions used
- **Email draft acceptance**: % of drafts sent as-is
- **Cost efficiency**: Cost per accepted suggestion
- **Time savings**: Estimated hours saved per week
