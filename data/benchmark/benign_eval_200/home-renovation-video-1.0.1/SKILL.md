---
name: home-renovation-video
version: "1.0.1"
displayName: "Home Renovation Video Maker"
description: >
  Describe your renovation project and NemoVideo creates the video. Kitchen remodels, bathroom updates, basement finishes, whole-house flips, single-room transformations — narrate the scope, the process, the challenges, and the final result, and get a renovation video that shows the full transformation story.

  Works by connecting to the NemoVideo AI backend at mega-api-prod.nemovideo.ai.
  Supports MP4, MOV, AVI, WebM.
homepage: https://nemovideo.com
repository: https://github.com/nemovideo/nemovideo_skills
license: MIT-0
---

## 0. First Contact

When the user opens this skill or sends their first message, **greet them immediately**:

> 🎥 Welcome! I can home renovation video for you. Share a video file or tell me your idea!

**Try saying:**
- "edit my video"
- "help me create a short video"
- "add effects to this clip"

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


# Home Renovation Video Maker — Create Before-and-After and DIY Remodel Content

Describe your renovation project and NemoVideo creates the video. Kitchen remodels, bathroom updates, basement finishes, whole-house flips, single-room transformations — narrate the scope, the process, the challenges, and the final result, and get a renovation video that shows the full transformation story.

## When to Use This Skill

Use this skill for home renovation and remodeling content:
- Create before-and-after transformation videos for completed renovation projects
- Film renovation progress documentation showing multi-week or multi-month builds
- Build project walkthrough content explaining decisions, materials, and costs
- Document DIY renovation tutorials for specific skills (tiling, drywalling, painting)
- Create home flip content for real estate investors and house flippers
- Produce budget renovation content showing cost-per-square-foot breakdowns

## How to Describe Your Renovation

Be specific about the scope, the timeline, the budget, the challenges, and the key transformation moments.

**Examples of good prompts:**
- "Kitchen renovation from 1970s to modern: 6-week project, $18,400 total. Before: original oak cabinets, laminate countertops, dropped ceiling with fluorescent lighting, beige tile floor. After: painted white shaker cabinets, quartz countertops, recessed lighting with pendant over island, LVP flooring throughout. The discovery moment when we opened the ceiling and found the original beams — we kept them exposed. The plumbing nightmare on week 3 that added 5 days and $2,200. Show the demo day, the beams reveal, the before/after counter transformation, and the final reveal."
- "One-day bathroom refresh, $800: Not a full remodel — just the things that make the biggest visual impact without touching plumbing. Mirror swap (old Hollywood strip lights → frameless backlit mirror), vanity paint (builder beige → deep charcoal), hardware swap (brushed nickel → matte black throughout), shower curtain and liner, new bath mat and towels. Before and after same angle. Total labor: 1 person, 9 hours. Show the transformation with time-lapse."
- "Basement finishing from bare concrete to livable space: 14-week DIY project, $22,000 materials + $8,000 labor for electrical and HVAC. Show the planning phase (moisture testing, design layout), framing the walls, insulation, electrical rough-in (hired out), drywall and mudding, LVP flooring, bar build, and final space: home theater, bar area, kids play zone. The moment the lights came on for the first time in the finished space."

## Key Parameters

| Parameter | Description | Example |
|-----------|-------------|---------|
| `renovation_type` | Project scope | `"full_kitchen"`, `"bathroom_refresh"`, `"basement_finish"`, `"room_makeover"`, `"whole_house"` |
| `budget` | Total project cost | `"$18,400"`, `"$800"`, `"$30,000"` |
| `timeline` | Project duration | `"1 day"`, `"6 weeks"`, `"14 weeks"` |
| `diy_level` | Work done yourself | `"full_diy"`, `"partial_diy"`, `"contractor_managed"` |
| `key_moments` | Highlight beats | `["ceiling beam reveal"`, `"plumbing nightmare"`, `"final reveal"]` |
| `show_costs` | Budget breakdown | `true` |
| `include_timelapse` | Fast-motion segments | `true` |
| `tone` | Content style | `"tutorial"`, `"documentary"`, `"before_after"`, `"budget_focused"` |
| `duration_minutes` | Video length | `5`, `10`, `15`, `20` |
| `platform` | Distribution | `"youtube"`, `"tiktok"`, `"instagram"` |

## Workflow

1. Describe the project scope, timeline, budget, and key moments
2. NemoVideo structures the renovation narrative (before → demo/process → challenges → reveal)
3. Cost overlays, timeline markers, and material callouts added automatically
4. Export with dramatic pacing suited to transformation content

## API Usage

### Kitchen Renovation Full Transformation

```bash
curl -X POST https://mega-api-prod.nemovideo.ai/v1/run \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "skill": "home-renovation-video",
    "input": {
      "prompt": "Full kitchen renovation, 8 weeks, $24,500: Before state — 1990s builder grade, oak cabinets with brass hardware, tile countertops, fluorescent box lighting, drop ceiling. Week 1: demo day (kept the bones, removed everything else). Week 2-3: new cabinet boxes installed, but the upper cabinet alignment took 3 attempts because the walls were out of plumb by an inch — show the measuring, the shimming, the problem-solving. Week 4: waterfall edge quartz countertop installation (one piece, crane required for the 9-foot island slab — dramatic). Week 5: tile backsplash (subway tile, 3 days of my worst grout work then 1 day of acceptable grout work). Week 6-7: appliance install, lighting (LED pendants over island, under-cabinet strips), and finish work. Week 8: the final reveal, cleaned and staged. The kitchen my family actually uses now.",
      "renovation_type": "full_kitchen",
      "budget": "$24,500",
      "timeline": "8 weeks",
      "diy_level": "partial_diy",
      "key_moments": ["demo day", "cabinet alignment problem", "crane slab install", "final reveal"],
      "show_costs": true,
      "include_timelapse": true,
      "tone": "documentary",
      "duration_minutes": 12,
      "platform": "youtube",
      "hashtags": ["KitchenRenovation", "HomeRenovation", "KitchenRemodel", "DIYKitchen", "HomeImprovement"]
    }
  }'
```

**Response:**
```json
{
  "job_id": "reno_abc123",
  "status": "processing",
  "estimated_seconds": 120,
  "poll_url": "https://mega-api-prod.nemovideo.ai/v1/jobs/reno_abc123"
}
```

### Budget Bathroom Refresh

```bash
curl -X POST https://mega-api-prod.nemovideo.ai/v1/run \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "skill": "home-renovation-video",
    "input": {
      "prompt": "Rental bathroom refresh under $600: The goal was maximum visual impact without any work that requires a permit or touches plumbing. Items: vanity light swap (old Hollywood bar → black industrial fixture, $89), mirror frame DIY (plain mirror + peel-and-stick tile surround, $40 in materials), cabinet paint (spray primer + 2 coats cabinet enamel in Repose Gray, $35 in supplies), hardware swap (8 pieces of brass → matte black, $45 for all), showerhead upgrade ($65 for a rain-style), grout pen on existing tile ($12, made 15-year-old tile look new), new towels and bath mat ($45). Total: $331. 6 hours of work. Show the before photo, each swap with cost overlay, and the after.",
      "renovation_type": "bathroom_refresh",
      "budget": "$331",
      "timeline": "1 day",
      "diy_level": "full_diy",
      "show_costs": true,
      "tone": "budget_focused",
      "duration_minutes": 7,
      "platform": "tiktok",
      "hashtags": ["BathroomMakeover", "BudgetRenovation", "RentalHacks", "HomeDecor", "DIYBathroom"]
    }
  }'
```

## Tips for Best Results

- **The specific obstacle makes the video**: "The walls were out of plumb by an inch" or "plumbing nightmare that added 5 days and $2,200" — the problem encountered and solved is more compelling than a smooth renovation
- **Real costs build trust**: Set `show_costs: true` and include the exact total — "$18,400" is more useful than "budget renovation"; viewers want to know if this is possible for their situation
- **The reveal needs setup**: Describe the "before" state in specific detail (not just "outdated kitchen" but "1970s oak cabinets, laminate countertops, dropped ceiling") — the transformation is only powerful if the baseline is clear
- **Discovery moments are shareable**: "When we opened the ceiling and found original beams" — the unexpected find during demolition or the problem that changed the plan is the emotional peak of renovation content
- **Timeline markers help viewers calibrate**: Set `include_timelapse: true` and describe what happened each week — viewers want to know how long things actually take

## Output Formats

| Platform | Resolution | Duration |
|----------|------------|----------|
| YouTube | 1920×1080 | 10–20 min |
| TikTok | 1080×1920 | 60–180s |
| Instagram Reels | 1080×1920 | 60–90s |
| Pinterest video | 1000×1500 | 15–60s |

## Related Skills

- `interior-design-video` — Design-focused room transformation content
- `diy-project-video` — Smaller scale DIY build content
- `room-makeover-video` — Single room transformation content
- `home-organization-video` — Post-renovation organization content

## Common Questions

**Should I film during the renovation or recreate it?**
Film during if possible — real-time documentation captures authentic problem-solving moments. If the project is complete, describe what happened week by week and NemoVideo reconstructs the narrative from your description and any photos taken during the project.

**How do I show a multi-week renovation in a 10-minute video?**
Set `include_timelapse: true` and structure the narrative by week or phase. NemoVideo compresses the timeline naturally — demo gets 60 seconds, framing gets 45 seconds, the discovery moment gets 2 minutes.

**Can I create renovation content for a house flip business?**
Yes — describe the investment context (purchase price, renovation budget, ARV target), the strategic decisions, and the result. Real estate investment renovation content is a strong YouTube sub-genre.
