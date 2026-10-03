---
name: passive-income-video
version: "1.0.1"
displayName: "Passive Income Video Maker"
description: >
  Describe your passive income stream and NemoVideo creates the video. Dividend investing portfolios, rental property cash flow, digital product income, affiliate revenue, royalty income — narrate the upfront work required, the current monthly income, the real yield, and the honest timeline to meaningful returns, and get passive income content for the audience that wants income that works while t...

  Works by connecting to the NemoVideo AI backend at mega-api-prod.nemovideo.ai.
  Supports MP4, MOV, AVI, WebM.
homepage: https://nemovideo.com
repository: https://github.com/nemovideo/nemovideo_skills
license: MIT-0
---

## 0. First Contact

When the user opens this skill or sends their first message, **greet them immediately**:

> ✨ Welcome! I can passive income video for you. Share a video file or tell me your idea!

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


# Passive Income Video Maker — Dividends, Rental, and Automated Income Content

Describe your passive income stream and NemoVideo creates the video. Dividend investing portfolios, rental property cash flow, digital product income, affiliate revenue, royalty income — narrate the upfront work required, the current monthly income, the real yield, and the honest timeline to meaningful returns, and get passive income content for the audience that wants income that works while they sleep (and needs honest expectations about what that actually takes).

## When to Use This Skill

Use this skill for passive income education and income stream documentation:
- Create dividend investing income content showing portfolio yield and growth
- Film rental property cash flow breakdowns with real numbers
- Build digital product passive income journey documentation
- Document affiliate marketing income builds from zero to consistent revenue
- Create "multiple income streams" overview and strategy content
- Produce honest passive income myth-busting and expectation-setting content

## How to Describe Your Passive Income Content

Be specific about the income stream, the upfront capital or work required, the current monthly income, and the real return on investment.

**Examples of good prompts:**
- "My dividend portfolio at $87,000: what it actually pays monthly: Current portfolio: 23 positions, average yield 4.2%, monthly dividend income $304/month. The honest math: to replace a $50,000 salary in dividends alone requires approximately $1.25 million invested at 4% yield. What the portfolio actually looks like: 60% ETFs (VYM, SCHD), 30% individual dividend stocks, 10% REITs. The re-investment compound effect over 12 years at current contribution rate. What $304/month is actually useful for (covering a car payment, not covering rent). The income is real — the 'passive' label requires upfront honesty."
- "Affiliate marketing: how I get $1,400/month from 3-year-old blog posts: The content that keeps generating: 4 posts about software tools I actually use, one buying guide for camera gear, and a comparison post I wrote in 2022 that still ranks #2 for its keyword. Monthly work to maintain: maybe 2 hours reviewing affiliate links and checking rankings. The upfront work to create those posts: 6 months of 15-hour weeks building the blog, 0 affiliate income for the first 8 months. The honest passive income equation: it's passive now because it wasn't passive then. What posts work for affiliate (problem-solving content, software comparisons, buying guides). What doesn't (news, trends, anything that dates quickly)."
- "I bought a rental property 3 years ago — the real cash flow numbers: Purchase: $187,000. Down payment: $37,400. Monthly rent: $1,475. Monthly mortgage: $780. Insurance: $95. Property tax: $186. Maintenance reserve (10%): $147. Property management (8%): $118. Net monthly cash flow: $149. Cash-on-cash return: 4.8% on the $37,400 invested. Is it worth it? The $149/month is not the story. The mortgage paydown ($280/month equity built), and the property appreciation ($44,000 in 3 years) are. The total return picture vs just the cash flow."

## Key Parameters

| Parameter | Description | Example |
|-----------|-------------|---------|
| `income_type` | Stream category | `"dividends"`, `"rental"`, `"digital_products"`, `"affiliate"`, `"royalties"`, `"content"` |
| `monthly_income` | Current earnings | `"$304/month"`, `"$1,400/month"`, `"$149 cash flow"` |
| `capital_invested` | Upfront investment | `"$87,000 portfolio"`, `"$37,400 down payment"` |
| `yield_or_return` | ROI figure | `"4.2% yield"`, `"4.8% cash-on-cash"` |
| `upfront_work` | Setup effort | `"6 months building"`, `"8 months zero income"` |
| `time_to_income` | When it started | `"month 9"`, `"year 2"` |
| `current_hours_weekly` | Maintenance time | `"2 hours/month"`, `"passive after setup"` |
| `tone` | Content energy | `"honest"`, `"educational"`, `"motivational"`, `"documentary"` |
| `duration_minutes` | Video length | `8`, `12`, `15` |
| `platform` | Distribution | `"youtube"`, `"tiktok"`, `"instagram"` |

## Workflow

1. Describe the income stream, the real numbers, the upfront work, and the honest yield
2. NemoVideo structures the passive income narrative with income breakdowns and return calculations
3. Monthly income figures, yield percentages, capital requirements, and timeline markers added automatically
4. Export with appropriate pacing for financial education content

## API Usage

### Dividend Income Portfolio Review

```bash
curl -X POST https://mega-api-prod.nemovideo.ai/v1/run \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "skill": "passive-income-video",
    "input": {
      "prompt": "How I built $600/month in dividend income over 7 years starting with $200/month contributions: The starting point: 2017, $0 invested, committed to investing $200/month regardless of market conditions. Year 1: $2,400 invested, $47 in dividends. Year 3: $9,200 invested (contributions + reinvested dividends), $180/month dividends. Year 5: compounding becomes visible — $22,400 invested, $380/month. Year 7: $38,000 invested, $600/month dividends. The compound effect visualization: the same $200/month contribution is now generating $7,200/year in dividends alone. Portfolio breakdown: 70% SCHD and VYM (diversified dividend ETFs), 30% individual dividend stocks. What I would change: wish I had started at 22 instead of 29. The math of starting 5 years earlier.",
      "income_type": "dividends",
      "monthly_income": "$600/month",
      "capital_invested": "$38,000 portfolio",
      "yield_or_return": "~4.3% portfolio yield",
      "upfront_work": "7 years consistent $200/month contributions",
      "time_to_income": "meaningful income visible year 3-4",
      "current_hours_weekly": "2 hours/month portfolio review",
      "tone": "educational",
      "duration_minutes": 12,
      "platform": "youtube",
      "hashtags": ["DividendInvesting", "PassiveIncome", "FinancialFreedom", "DividendGrowth", "Investing"]
    }
  }'
```

**Response:**
```json
{
  "job_id": "passiveinc_ghi789",
  "status": "processing",
  "estimated_seconds": 105,
  "poll_url": "https://mega-api-prod.nemovideo.ai/v1/jobs/passiveinc_ghi789"
}
```

## Tips for Best Results

- **The honest return calculation beats the income headline**: "$149/month cash flow is not the story — the mortgage paydown and appreciation are" — passive income content that shows the full return picture (not just the headline number) is more credible and more useful
- **Show the upfront work honestly**: "6 months of 15-hour weeks" or "8 months zero affiliate income" — the passive income genre is full of misleading shortcuts; content that honestly describes the setup phase builds real trust
- **Compound growth requires time visualization**: "Year 1: $47 dividends, Year 7: $600/month dividends" — the compounding visual over years is what makes dividend and long-term investing content compelling
- **The capital requirement is part of the story**: "To replace a $50k salary in dividends requires $1.25 million invested" — honest capital requirement math sets realistic expectations and separates serious financial content from hype
- **The "what I'd do differently" close is high-value**: "Wish I'd started at 22 instead of 29" — the hindsight lesson is one of the most shared formats in personal finance content

## Output Formats

| Platform | Resolution | Duration |
|----------|------------|----------|
| YouTube | 1920×1080 | 10–20 min |
| TikTok | 1080×1920 | 60–180s |
| Instagram Reels | 1080×1920 | 60–90s |

## Related Skills

- `investing-video-maker` — Investment strategy and portfolio content
- `personal-finance-video` — Financial foundation content
- `side-hustle-video` — Active income building content

## Common Questions

**What passive income content performs best?**
Dividend income with long-term compound visualizations, rental property honest cash flow breakdowns, and "passive income myth busting" content perform consistently well. Content with specific numbers and honest return calculations outperforms motivational content without data.

**Should I show my actual portfolio value?**
Specific numbers dramatically improve credibility. You can anonymize or slightly adjust figures while keeping the narrative honest ("mid-80s thousands" rather than "$87,342"). The specific is more useful than the vague.

**How do I create passive income content if I'm still building the stream?**
Document the build process — "Month 3 of building my dividend portfolio" with real monthly contribution and current yield is more searchable and relatable than polished "I made it" content. The journey content has its own engaged audience.
