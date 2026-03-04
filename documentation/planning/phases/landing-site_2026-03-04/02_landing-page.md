# Phase 02 — Landing Page

**Status**: 📋 PENDING
**Effort**: Medium
**Dependencies**: Phase 01 (Project Scaffold)

## Goal

Build the public marketing landing page that sells Storyline AI to established creators with large content libraries. The page should make the product feel simple, the Telegram workflow feel natural, and the value proposition feel obvious.

## Core Messaging

**Primary angle**: "You already have the content. Storyline keeps it working for you."

**Target user**: Established creators / small brands with 100-5000+ pieces of content sitting in Google Drive, who post Stories inconsistently or not at all because it's tedious.

**Key emotions to evoke**:
- Relief ("I don't have to think about Stories anymore")
- Confidence ("My content stays visible without daily effort")
- Curiosity ("Telegram? That's clever.")

**What we're NOT saying**:
- Not a content creation tool (you already have content)
- Not a full social media manager (this is Stories-specific)
- Not competing on analytics or AI captions (yet)

## Page Structure

All sections are components in `src/components/landing/`. The page (`src/app/page.tsx`) composes them.

---

### Section 1: Hero

**Component**: `src/components/landing/hero.tsx`

**Layout**: Full-width, centered text, gradient or subtle background

**Content**:
- **Headline**: "Keep Your Stories Alive" (or similar — short, emotional, outcome-focused)
- **Subheadline**: "You have hundreds of photos and videos sitting idle. Storyline automatically rotates them through your Instagram Stories — so your content keeps working while you don't."
- **CTA**: Waitlist form (email input + submit button) — inline, not a separate page
- **Social proof line** (below CTA): "Free during beta • No credit card required" or "Join N creators on the waitlist" (once you have signups)

**Design notes**:
- Keep it clean, not busy. One clear action.
- Mobile: stack vertically, CTA full-width
- Desktop: can add a subtle hero image/illustration on the right (phone showing a Story feed)

---

### Section 2: How It Works

**Component**: `src/components/landing/how-it-works.tsx`

**Layout**: 3-step horizontal (desktop) / vertical (mobile) with numbered cards or icons

**Content**:

| Step | Title | Description | Icon/Visual |
|------|-------|-------------|-------------|
| 1 | Connect Your Drive | Link your Google Drive folder. Storyline indexes your content library and organizes it by category. | Cloud/folder icon |
| 2 | Set Your Schedule | Choose how many Stories per day and when. Storyline fills your queue automatically — prioritizing fresh content. | Calendar/clock icon |
| 3 | Approve via Telegram | Get a preview in Telegram before each post goes live. Tap to approve, skip, or let it auto-post. | Telegram icon + checkmark |

**Design notes**:
- Use Lucide icons for consistency
- Each step should have a subtle connecting line/arrow between them
- Keep descriptions to 1-2 sentences max
- Optional: animated entrance on scroll

---

### Section 3: Telegram Preview

**Component**: `src/components/landing/telegram-preview.tsx`

**Layout**: Split — text on one side, mockup/screenshot on the other

**Content**:
- **Heading**: "Your Stories, Your Schedule, Your Approval"
- **Body**: "Every scheduled Story lands in your Telegram chat with a preview. Tap a button to post it, skip it, or let Storyline handle it automatically. No app to open. No dashboard to check. It just works."
- **Visual**: Screenshot or stylized mockup of a Telegram message showing:
  - A Story image preview
  - Caption text
  - Four buttons: ✅ Posted, ⏭️ Skip, ❌ Reject, 🤖 Auto Post
  - A notification badge showing "3 Stories scheduled today"

**Design notes**:
- This section sells the Telegram angle — it needs to feel elegant, not hacky
- The mockup should look like a real Telegram conversation (dark mode preferred, matches Telegram's native look)
- Consider a slight phone-frame around the mockup
- If real screenshots aren't polished enough, create a styled HTML mockup that looks like Telegram

---

### Section 4: Features

**Component**: `src/components/landing/features.tsx`

**Layout**: 2x3 grid of feature cards (desktop) / single column (mobile)

**Features**:

| Feature | Title | Description |
|---------|-------|-------------|
| 📁 | Your Cloud, Your Content | Connect Google Drive and point to your media folder. Storyline syncs automatically — no uploads, no transfers. |
| 🔄 | Smart Rotation | Never-posted content goes first. Storyline tracks what's been shared and keeps your library cycling evenly. |
| 📊 | Category Mixing | Organize content into folders (memes, products, behind-the-scenes) and set ratios. Storyline maintains the mix. |
| 👥 | Multi-Account | Manage multiple Instagram accounts from one place. Switch between brands in a tap. |
| 🕐 | Flexible Scheduling | Set posts per day, posting windows, and jitter. Stories go out at natural times, not robotic intervals. |
| 🔒 | Self-Hosted Media | Your content stays in your Google Drive. Storyline never stores your media permanently — it streams from your cloud. |

**Design notes**:
- Use shadcn `Card` component
- Lucide icons (not emoji — the emoji above are just for this doc)
- Keep descriptions to 2 lines max
- Subtle hover effect on cards

---

### Section 5: Pricing Teaser

**Component**: `src/components/landing/pricing.tsx`

**Layout**: Single centered card or minimal section

**Content**:
- **Heading**: "Free While in Beta"
- **Body**: "Storyline AI is in early access. Join the waitlist and be among the first to try it — completely free. We'll figure out pricing together."
- **Optional detail list**:
  - ✓ Unlimited Stories
  - ✓ Google Drive integration
  - ✓ Multi-account support
  - ✓ Telegram-powered workflow
- **CTA**: "Join the Waitlist" (scrolls to hero or opens inline form)

**Design notes**:
- Don't overthink pricing at this stage — the point is to signal "this won't cost you much"
- Keep it honest and human ("we'll figure out pricing together")

---

### Section 6: FAQ

**Component**: `src/components/landing/faq.tsx`

**Layout**: Accordion (use shadcn `Accordion` component)

**Questions**:

| Question | Answer |
|----------|--------|
| What is Storyline AI? | Storyline is an Instagram Story automation tool that keeps your content library active. Connect your Google Drive, set a schedule, and approve posts via Telegram. |
| Why Telegram? | Telegram is fast, lightweight, and always open. Instead of logging into another dashboard, you get Story previews right in your messages. Tap a button to approve — it takes 2 seconds. |
| Do I need a business Instagram account? | Yes. Instagram's API requires a Business or Creator account connected to a Facebook Page. Our setup guide walks you through it step by step. |
| What content formats are supported? | JPG, PNG, and GIF images optimized for Instagram Stories (9:16 aspect ratio). We automatically validate and resize your media. |
| Where is my content stored? | In your Google Drive — always. Storyline syncs from your folder but never permanently stores your media. You stay in control. |
| Is this free? | Yes, during the beta period. We'll announce pricing before any charges — early users will get the best deal. |
| How do I get started? | Join the waitlist below. We'll send you an invite with a setup guide when your spot opens up. |
| Who built this? | Hi! I'm Chris. You can find me at [crog.gg](https://crog.gg) or reach out at christophertrogers37@gmail.com. |

---

### Section 7: Final CTA

**Component**: `src/components/landing/final-cta.tsx`

**Layout**: Full-width section with background color/gradient, centered text

**Content**:
- **Heading**: "Ready to put your content to work?"
- **Subheading**: "Join the waitlist and be first in line."
- **CTA**: Waitlist form (same component as hero, reused)
- **Contact line**: "Questions? Reach out at [crog.gg](https://crog.gg) or christophertrogers37@gmail.com"

---

## Shared Components

### Waitlist Form

**Component**: `src/components/landing/waitlist-form.tsx`

Used in Hero (Section 1) and Final CTA (Section 7). Inline form, not a modal.

**Fields**:
- Email (required) — input with validation
- Submit button — "Join the Waitlist"

**States**:
- Default: input + button
- Loading: button shows spinner
- Success: "You're on the list! We'll be in touch." (replaces form)
- Error: "Something went wrong. Try again?" (inline error message)
- Duplicate: "You're already on the list!" (friendly, not an error)

**Behavior**:
- POST to `/api/waitlist` (Phase 03)
- Client-side email validation before submit
- Disable button during submission
- No page reload — handle via fetch + state

### Header

**Component**: `src/components/layout/header.tsx`

- Logo (text or image): "Storyline AI"
- Minimal nav: no links for now (single-page site)
- Right side: "Join Waitlist" button (scrolls to hero form)
- Sticky on scroll with backdrop blur
- Mobile: same layout, no hamburger needed (only one CTA)

### Footer

**Component**: `src/components/layout/footer.tsx`

- Left: "© 2026 Storyline AI"
- Center or right: "Built by [Chris](https://crog.gg) • [Contact](mailto:christophertrogers37@gmail.com)"
- Keep minimal — this isn't a multi-page site yet

---

## Static Assets Needed

Before building, gather or create:

1. **Telegram mockup** — Screenshot or HTML recreation of a Story notification in Telegram with buttons
2. **Hero visual** (optional) — Phone frame showing a Story feed, or abstract illustration
3. **OG image** — 1200x630 social share image for link previews
4. **Favicon** — Simple icon/logo

> These don't need to be perfect for v1. Placeholder images with the right dimensions are fine — polish later.

## Responsive Breakpoints

- Mobile: 375px (single column, full-width CTAs)
- Tablet: 768px (2-column where applicable)
- Desktop: 1280px (max-width container, comfortable spacing)

## Performance Targets

- All sections are static (no client-side data fetching except waitlist form)
- Aim for 95+ Lighthouse score
- Use Next.js `Image` component for all images
- No heavy JS libraries — keep bundle minimal

## Acceptance Criteria

- [ ] All 7 sections render correctly on mobile and desktop
- [ ] Waitlist form submits successfully (requires Phase 03 API)
- [ ] FAQ accordion expands/collapses smoothly
- [ ] Page loads in < 2 seconds
- [ ] OG metadata renders correctly in link previews
- [ ] No horizontal scroll on any breakpoint
- [ ] Contact links work (crog.gg, email)
- [ ] "Join Waitlist" button in header scrolls to form
