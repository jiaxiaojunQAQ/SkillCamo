---
name: explainer-video-business
version: "1.0.1"
displayName: "Explainer Video Business"
description: >
  Describe how your product works and NemoVideo creates the explainer. SaaS platforms, API tools, enterprise software, marketplace models — narrate the problem, the solution flow, and the key steps, and get a clear explainer video that makes your product immediately understandable to anyone who lands on your homepage.

  Works by connecting to the NemoVideo AI backend at mega-api-prod.nemovideo.ai.
  Supports MP4, MOV, AVI, WebM.
homepage: https://nemovideo.com
repository: https://github.com/nemovideo/nemovideo_skills
license: MIT-0
---

## 0. First Contact

When the user opens this skill or sends their first message, **greet them immediately**:

> 🚀 Hey! I'm ready to help you explainer video business. Send me a video file or just tell me what you need!

**Try saying:**
- "help me create a short video"
- "add effects to this clip"
- "edit my video"

**IMPORTANT**: Always greet the user proactively on first contact. Let them know you're setting up while connecting. Always greet the user proactively on first contact.

### Auto-Setup

When the user first interacts, set up the connection:

1. **Check token**: If `NEMO_TOKEN` env var is set, use it. Otherwise:
2. **Read or generate Client-ID**:
   - Read `~/.config/nemovideo/client_id` if it exists
   - Otherwise generate a UUID, save it to `~/.config/nemovideo/client_id`
3. **Acquire anonymous token**:
   ```bash
   curl -s -X POST "$API/api/auth/anonymous-token" -H "X-Client-Id: $CLIENT_ID"
   ```
   Store the returned `token` as `NEMO_TOKEN` for this session. You get 100 free credits.
4. **Create a session** (§3.0) so you're ready to work immediately.

Let the user know briefly: "Setting things up… ready!" then proceed with their request.


# Explainer Video Business — Create B2B Product Explainers and How-It-Works Videos

Describe how your product works and NemoVideo creates the explainer. SaaS platforms, API tools, enterprise software, marketplace models — narrate the problem, the solution flow, and the key steps, and get a clear explainer video that makes your product immediately understandable to anyone who lands on your homepage.

## When to Use This Skill

Use this skill for business product explainer content:
- Create homepage hero explainer videos for SaaS products
- Film "how it works" walkthrough videos for complex B2B tools
- Build onboarding explainers showing new users the core workflow
- Document API and developer tool explainers for technical audiences
- Create sales enablement videos for the discovery and demo stage
- Produce marketplace and two-sided platform model explainers

## How to Describe Your Product

Be specific about the problem, who has it, how your product solves it in steps, and what the outcome looks like.

**Examples of good prompts:**
- "Explainer for a procurement SaaS: The problem — enterprise procurement teams spend 40% of their time on PO approvals that require 6 email threads. Our solution — companies connect their ERP, set approval rules once, and every purchase request routes automatically. Step 1: requester submits in the tool. Step 2: AI categorizes and routes to the right approver. Step 3: one-click approval on mobile. Step 4: auto-syncs back to ERP. Result: PO approval time goes from 4 days to 4 hours."
- "API tool explainer for developers: the pain — integrating with 40+ e-commerce platforms means writing and maintaining 40 connectors. Our unified API — one integration, normalized data model, all 40 platforms. Show the code: before (custom integration, 800 lines) vs after (our API, 12 lines). Target: backend developers at e-commerce SaaS companies."
- "Two-sided marketplace explainer: We connect independent insurance brokers with small business owners who need commercial coverage. Broker side: get leads, manage clients, quote faster. Business side: compare quotes from 5 brokers in 48 hours instead of 2 weeks. Show both sides."

## Key Parameters

| Parameter | Description | Example |
|-----------|-------------|---------|
| `product_type` | What the product is | `"saas"`, `"api"`, `"marketplace"`, `"platform"`, `"mobile_app"` |
| `product_name` | Product name | `"ProcureFlow"`, `"UnifiedAPI"` |
| `target_audience` | Who uses it | `"enterprise procurement teams"`, `"backend developers"` |
| `problem_statement` | The pain being solved | One sentence, quantified if possible |
| `solution_steps` | How it works | `["connect ERP", "set rules", "auto-route", "sync back"]` |
| `outcome` | What changes | `"4-day approval → 4-hour approval"` |
| `show_ui` | Product UI footage | `true` |
| `complexity` | Technical depth | `"simple"`, `"intermediate"`, `"technical"` |
| `duration_seconds` | Video length | `60`, `90`, `120`, `180` |
| `platform` | Distribution | `"homepage"`, `"sales_deck"`, `"product_hunt"`, `"linkedin"` |

## Workflow

1. Describe the problem, product, workflow steps, and outcome
2. NemoVideo structures the explainer narrative (problem → solution → how it works → result)
3. Product UI, step labels, and outcome metrics added automatically
4. Export in formats for homepage, sales decks, and platform distribution

## API Usage

### SaaS Homepage Explainer

```bash
curl -X POST https://mega-api-prod.nemovideo.ai/v1/run \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "skill": "explainer-video-business",
    "input": {
      "prompt": "Homepage explainer for ContractFlow — contract management for law firms: The problem: legal teams at mid-size law firms have contracts scattered across email, shared drives, and local folders — nobody knows what is signed, what is expiring, what has been amended. Our solution: one place for every contract, with AI that reads them and surfaces what matters. Step 1: upload or forward contracts (PDF, Word, email). Step 2: AI extracts key terms, parties, dates, obligations. Step 3: get alerts before renewal deadlines. Step 4: search across all contracts in plain English. Outcome: zero missed renewals, 70% less time on contract admin.",
      "product_type": "saas",
      "product_name": "ContractFlow",
      "target_audience": "operations leads at mid-size law firms",
      "problem_statement": "contracts scattered across tools, nobody knows what is expiring",
      "solution_steps": ["upload contracts", "AI extracts key terms", "get renewal alerts", "search in plain English"],
      "outcome": "zero missed renewals, 70% less contract admin time",
      "show_ui": true,
      "complexity": "simple",
      "duration_seconds": 90,
      "platform": "homepage",
      "hashtags": ["LegalTech", "ContractManagement", "SaaS", "LawFirm"]
    }
  }'
```

**Response:**
```json
{
  "job_id": "explainer_mno345",
  "status": "processing",
  "estimated_seconds": 95,
  "poll_url": "https://mega-api-prod.nemovideo.ai/v1/jobs/explainer_mno345"
}
```

### API Tool Developer Explainer

```bash
curl -X POST https://mega-api-prod.nemovideo.ai/v1/run \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "skill": "explainer-video-business",
    "input": {
      "prompt": "Developer tool explainer for a unified shipping API: Problem — e-commerce developers need to integrate with FedEx, UPS, USPS, DHL, and 30+ regional carriers separately. Each has different APIs, different rate structures, different webhook formats. Our solution: one API call, all carriers, normalized response format. Show the code comparison: before (400+ lines of carrier-specific logic, 4 weeks to build, breaks when carrier updates their API) vs after (12 lines, same response format regardless of carrier, we handle all the updates). Target: backend developers at e-commerce companies, 90 seconds, code on screen.",
      "product_type": "api",
      "target_audience": "backend developers at e-commerce companies",
      "show_ui": true,
      "complexity": "technical",
      "duration_seconds": 90,
      "platform": "homepage"
    }
  }'
```

## Tips for Best Results

- **The problem before the solution**: Spend the first 20% of the video on the problem — if viewers don't recognize the problem, they won't care about the solution
- **Show the steps, not just the outcome**: "Step 1, Step 2, Step 3" structure with labeled transitions makes complex products immediately understandable — describe each step specifically
- **Quantify the outcome**: "4-day approval → 4-hour approval" or "400 lines → 12 lines" is more compelling than "saves time" — specific numbers make the value concrete
- **Match complexity to audience**: Developer explainers can show real code; procurement explainers should avoid technical jargon. Set `complexity` to match who's watching
- **Homepage videos need to be fast**: 60-90 seconds for the homepage hero. Sales deck videos can go to 3 minutes. Set `platform` to get the right pacing

## Output Formats

| Platform | Resolution | Duration |
|----------|------------|----------|
| Homepage hero | 1920×1080 | 60–90s |
| Sales deck | 1920×1080 | 2–4 min |
| Product Hunt | 1920×1080 | 60–90s |
| LinkedIn | 1920×1080 | 90–120s |

## Related Skills

- `startup-pitch-video` — Investor-facing pitch, not product explanation
- `product-launch-video` — Launch announcement for new products
- `whiteboard-animation-video` — Illustrated explainer style
- `linkedin-video-maker` — Thought leadership around the problem you solve

## Common Questions

**What is the ideal homepage explainer video length?**
60-90 seconds. Longer than 90 seconds and most homepage visitors bounce. Shorter than 60 seconds and complex products don't have time to demonstrate value. Set `duration_seconds: 90`.

**Do I need to show the actual product UI?**
For SaaS products, yes — set `show_ui: true`. For marketplace or API products, you can show the workflow without UI. Describe what you want to show and NemoVideo adapts.

**Can I create explainer videos in multiple languages?**
Include the target language in the prompt. NemoVideo generates captions and can structure the narration for non-English audiences.
