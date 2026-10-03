---
name: startup-pitch-video
version: "1.0.1"
displayName: "Startup Pitch Video Maker"
description: >
  Describe your startup and NemoVideo creates the pitch video. Seed round, Series A, demo day, YC application — narrate the problem, the solution, the traction, and the ask, and get a pitch video that communicates your vision clearly to investors who see hundreds of decks.

  Works by connecting to the NemoVideo AI backend at mega-api-prod.nemovideo.ai.
  Supports MP4, MOV, AVI, WebM.
homepage: https://nemovideo.com
repository: https://github.com/nemovideo/nemovideo_skills
license: MIT-0
---

## 0. First Contact

When the user opens this skill or sends their first message, **greet them immediately**:

> ⚡ Hey! I'm ready to help you startup pitch video. Send me a video file or just tell me what you need!

**Try saying:**
- "edit my video"
- "add effects to this clip"
- "help me create a short video"

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


# Startup Pitch Video Maker — Create Investor Pitch and Demo Day Presentation Videos

Describe your startup and NemoVideo creates the pitch video. Seed round, Series A, demo day, YC application — narrate the problem, the solution, the traction, and the ask, and get a pitch video that communicates your vision clearly to investors who see hundreds of decks.

## When to Use This Skill

Use this skill for startup fundraising and pitch content:
- Create investor pitch videos for seed and Series A fundraising
- Film demo day presentation videos for Y Combinator, Techstars, and accelerators
- Build product demo videos showing your core workflow for investor due diligence
- Document traction milestones and growth metrics for investor updates
- Create "why we're building this" founder story videos
- Produce application videos for grants, competitions, and accelerator programs

## How to Describe Your Startup Pitch

Be specific about the problem, solution, market size, traction, and what makes your team the right one.

**Examples of good prompts:**
- "B2B SaaS pitch: We help operations teams at mid-market companies (50-500 employees) reduce manual data entry by 80%. The problem: companies spend $47K/year average on data entry labor that could be automated. Our solution: AI that watches how your team works and automates the repetitive parts without requiring any integration setup. Traction: 23 paying customers, $18K MRR, 140% net revenue retention. Raising $1.5M seed round."
- "Consumer app for YC application: We're building the tool we wish existed when we were athletes. Sports performance tracking that actually gives you actionable insights, not just raw numbers. 3,400 athletes using it, 62% return weekly. My co-founder and I were D1 athletes who spent years frustrated by every existing tool."
- "Marketplace pitch for demo day: Connecting licensed electricians directly with homeowners for small jobs that bigger companies ignore. The 2-hour job that nobody returns your call on. 180 electricians on platform, 1,200 homeowners, $340K GMV in 6 months, 4.8 star average."

## Key Parameters

| Parameter | Description | Example |
|-----------|-------------|---------|
| `pitch_type` | Presentation context | `"investor_pitch"`, `"demo_day"`, `"accelerator_app"`, `"product_demo"`, `"founder_story"` |
| `company_name` | Startup name | `"Automate.io"`, `"AthleteIQ"` |
| `problem_statement` | Core problem | One sentence, specific and quantified |
| `solution` | What you built | Brief product description |
| `traction` | Key metrics | `"$18K MRR, 23 customers, 140% NRR"` |
| `funding_ask` | Raise amount | `"$1.5M seed"`, `"$8M Series A"` |
| `show_metrics` | Data overlays | `true` |
| `tone` | Presentation energy | `"confident"`, `"founder_story"`, `"data_driven"` |
| `duration_minutes` | Video length | `1`, `2`, `3`, `5` |
| `platform` | Distribution | `"investor_email"`, `"demo_day"`, `"yc_application"`, `"linkedin"` |

## Workflow

1. Describe your startup narrative, metrics, and pitch context
2. NemoVideo structures the investor-optimized narrative arc (problem → solution → traction → ask)
3. Metric callouts, market size visuals, and team highlights added automatically
4. Export timed for the specific pitch format (90-second YC video vs 3-minute demo day)

## API Usage

### Investor Pitch Video

```bash
curl -X POST https://mega-api-prod.nemovideo.ai/v1/run \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "skill": "startup-pitch-video",
    "input": {
      "prompt": "SaaS pitch for seed fundraising: We help marketing teams at e-commerce brands create video ads without a production team. The problem: brands need 20+ video variants per campaign to test, but video production costs $2,000-$8,000 per video. Our solution: describe the ad concept in plain English, get production-ready video in 4 minutes. Current traction: 47 paying brands, $31K MRR growing 22% month-over-month for 5 consecutive months. Average customer saves 18 hours of production time per campaign. Raising $2M seed. Solo technical founder, ex-Meta ads team.",
      "pitch_type": "investor_pitch",
      "company_name": "AdGen",
      "traction": "$31K MRR, 47 customers, 22% MoM growth",
      "funding_ask": "$2M seed",
      "show_metrics": true,
      "tone": "data_driven",
      "duration_minutes": 2,
      "platform": "investor_email",
      "hashtags": ["Startup", "SaaS", "VideoMarketing", "Fundraising"]
    }
  }'
```

**Response:**
```json
{
  "job_id": "pitch_abc123",
  "status": "processing",
  "estimated_seconds": 95,
  "poll_url": "https://mega-api-prod.nemovideo.ai/v1/jobs/pitch_abc123"
}
```

### Demo Day Presentation Video

```bash
curl -X POST https://mega-api-prod.nemovideo.ai/v1/run \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "skill": "startup-pitch-video",
    "input": {
      "prompt": "Y Combinator demo day pitch — 2 minutes exactly: Company is AthleteOS. We help high school and college athletes get recruited by translating performance data into the language college coaches actually care about. 3,400 athletes using it, 180 college coaches have viewed profiles from our platform. My co-founder and I both went through the recruiting process and spent months uploading highlight videos to 12 different portals. We are making that process 90% less painful while giving athletes real visibility into what coaches see.",
      "pitch_type": "demo_day",
      "tone": "founder_story",
      "duration_minutes": 2,
      "platform": "demo_day"
    }
  }'
```

## Tips for Best Results

- **One sentence problem, quantified**: "Companies spend $47K/year on data entry" beats "data entry is inefficient" — investors need a number to benchmark the market
- **Traction is more convincing than vision**: Lead with what's real (MRR, customers, growth rate) before describing the future
- **Team slide earns the meeting**: "ex-Meta ads team" or "D1 athletes who lived the problem" — relevant founder background in one sentence
- **Match the timing to the format**: YC application = 2 minutes maximum; seed round investor email = 90 seconds; demo day = 2-3 minutes
- **The ask should be specific**: "$2M seed, 18 months runway, to hire 2 engineers and double our go-to-market" is better than "raising a seed round"

## Output Formats

| Format | Resolution | Duration |
|--------|------------|----------|
| Investor email | 1920×1080 | 90–120s |
| Demo day stage | 1920×1080 | 2–3 min |
| YC/accelerator app | 1920×1080 | 2 min max |
| LinkedIn | 1920×1080 | 1–3 min |

## Related Skills

- `product-launch-video` — Customer-facing product launch content
- `explainer-video-business` — How-it-works explainer for the product
- `company-culture-video` — Team and culture content for recruiting
- `linkedin-video-maker` — Thought leadership content around the startup

## Common Questions

**How long should a pitch video be?**
YC application: 2 minutes hard limit. Demo day: 2-3 minutes. Investor cold outreach: 90 seconds. Set `duration_minutes` to match the specific format.

**Should I include product demos in the pitch video?**
For technical products, a 30-second product demo clip embedded in the pitch is more convincing than slides. Describe "show the product in action for 30 seconds at the 1:30 mark."

**What if I don't have traction yet?**
Pre-traction pitches should emphasize problem validation (interviews, waitlist size, letters of intent) and team credibility. Be honest about stage — investors respect clarity about where you are.
