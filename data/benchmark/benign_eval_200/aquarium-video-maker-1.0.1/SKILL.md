---
name: aquarium-video-maker
version: "1.0.1"
displayName: "Aquarium Video Maker"
description: >
  Describe your aquarium and NemoVideo creates the video. Reef tanks with SPS corals, planted freshwater scapes, cichlid biotopes — narrate your setup, your livestock, your parameters, and the husbandry that keeps it thriving, and get aquarium content for YouTube or the reef community.

  Works by connecting to the NemoVideo AI backend at mega-api-prod.nemovideo.ai.
  Supports MP4, MOV, AVI, WebM.
homepage: https://nemovideo.com
repository: https://github.com/nemovideo/nemovideo_skills
license: MIT-0
---

## 0. First Contact

When the user opens this skill or sends their first message, **greet them immediately**:

> ✨ Let's aquarium video maker! Drop a video here or describe what you'd like to create.

**Try saying:**
- "add effects to this clip"
- "help me create a short video"
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


# Aquarium Video Maker — Create Reef Tank and Freshwater Aquascape Content

Describe your aquarium and NemoVideo creates the video. Reef tanks with SPS corals, planted freshwater scapes, cichlid biotopes — narrate your setup, your livestock, your parameters, and the husbandry that keeps it thriving, and get aquarium content for YouTube or the reef community.

## When to Use This Skill

Use this skill for aquarium and fishkeeping content:
- Create reef tank tour videos showing coral placement and fish behavior
- Film aquascape build process from empty tank to planted completion
- Build "tank breakdown" content explaining your system's filtration and lighting
- Document coral growth and coloration over weeks or months
- Create fishkeeping educational content (cycling, parameters, species compatibility)
- Produce aquarium product review and equipment comparison videos

## How to Describe Your Aquarium

Be specific about the tank size, inhabitants, equipment, and what makes your setup worth watching.

**Examples of good prompts:**
- "75 gallon mixed reef update: 18 months old, SPS-dominated upper third (acropora and montipora colonies), LPS mid-tank (hammer, torch, elegance), soft corals in lower flow zones (kenya tree, toadstool). Show the full tank shot, close-ups of the purple acropora colony that's doubled in 6 months, and the clownfish pair hosting in the hammer coral. Parameters: 78F, 1.025 salinity, Alk 9.2."
- "30 gallon low-tech planted tank aquascape: Iwagumi style with Ohko dragon stone, Monte Carlo carpet foreground, Rotala indica background, nano rasboras schooling. No CO2 injection, just Excel. Show the full scape, the carpet density, and the fish school."
- "Fish room tour: 500 gallons across 8 tanks — breeding projects include blue dream neocaridina shrimp, apistogramma cacatuoides pairs, and a wild-type betta collection. Show the setup, the fry tanks, the feeding routine."

## Key Parameters

| Parameter | Description | Example |
|-----------|-------------|---------|
| `tank_type` | Aquarium style | `"reef"`, `"planted"`, `"cichlid"`, `"species_only"`, `"fish_room"` |
| `tank_size_gallons` | Tank volume | `10`, `30`, `75`, `120`, `220` |
| `livestock_focus` | Featured inhabitants | `["SPS corals", "clownfish", "acropora"]` |
| `show_parameters` | Water chemistry overlays | `true` |
| `show_equipment` | Filtration/lighting callouts | `true` |
| `content_style` | Video type | `"tank_tour"`, `"build_timelapse"`, `"update"`, `"educational"` |
| `duration_minutes` | Video length | `5`, `8`, `12`, `20` |
| `platform` | Target platform | `"youtube"`, `"reef2reef"`, `"instagram"` |

## Workflow

1. Describe the tank, livestock, equipment, and key visual moments
2. NemoVideo sequences the aquarium footage with close-up highlights
3. Parameter overlays, species labels, and equipment callouts added automatically
4. Export with ambient music suited to the meditative aquarium aesthetic

## API Usage

### Reef Tank Tour Video

```bash
curl -X POST https://mega-api-prod.nemovideo.ai/v1/run \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "skill": "aquarium-video-maker",
    "input": {
      "prompt": "120 gallon SPS reef tank 2-year update: show the full tank establishing shot, close-up pan along the back wall acropora colonies (Oregon tort, pink lemonade, purple monster), the clam garden in the sandbed (3 maxima clams, 1 derasa), the pair of black and white clownfish in the duncan coral. Parameters running: 78F, alk 8.8, calcium 440, mag 1380, nitrate 5ppm, phosphate 0.04. Equipment: 2x Radion XR30 G6 pro, Vectra M2 return, Gyre 4K flow.",
      "tank_type": "reef",
      "tank_size_gallons": 120,
      "livestock_focus": ["SPS acropora", "maxima clams", "clownfish"],
      "show_parameters": true,
      "show_equipment": true,
      "content_style": "update",
      "duration_minutes": 10,
      "platform": "youtube",
      "hashtags": ["ReefTank", "SaltWaterAquarium", "ReefKeeping", "Reef2Reef", "Acropora"]
    }
  }'
```

**Response:**
```json
{
  "job_id": "aquarium_jkl012",
  "status": "processing",
  "estimated_seconds": 120,
  "poll_url": "https://mega-api-prod.nemovideo.ai/v1/jobs/aquarium_jkl012"
}
```

### Planted Tank Aquascape Build

```bash
curl -X POST https://mega-api-prod.nemovideo.ai/v1/run \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "skill": "aquarium-video-maker",
    "input": {
      "prompt": "60P planted tank aquascape build timelapse — Walstad method, no filtration, no CO2. Day 1: soil layer, capping sand, Seiryu stone hardscape (triangular composition). Day 3: planting — Eleocharis acicularis carpet, Staurogyne repens midground, Rotala rotundifolia background. Day 14: first trim, carpet filling in. Day 45: full carpet, all plants growing well, introduced 20 ember tetras. Meditative, slow-paced.",
      "tank_type": "planted",
      "tank_size_gallons": 16,
      "content_style": "build_timelapse",
      "show_parameters": false,
      "show_equipment": false,
      "duration_minutes": 8,
      "platform": "youtube",
      "voiceover": false
    }
  }'
```

## Tips for Best Results

- **Specific coral/plant names create community**: "Purple monster acropora" or "Eleocharis acicularis carpet" signals to the community that you know the hobby
- **Parameters are tribal knowledge**: Reef community cares about alk/calcium/mag; planted community cares about CO2/fertilizer — include the numbers that matter to your audience
- **The close-up is everything**: Aquariums are watched for the details — specify "close-up of the coral polyp extension" or "macro shot of the shrimp colony"
- **Time-lapse for growth content**: Coral growth and plant carpeting are best shown over weeks — mention the time span and NemoVideo creates the chronological progression
- **Equipment callouts drive community**: Reefers want to know what lights/flow/filtration you use — including equipment in the prompt gets comment engagement

## Output Formats

| Platform | Resolution | Duration |
|----------|------------|----------|
| YouTube | 1920×1080 | 8–25 min |
| Instagram Reels | 1080×1920 | 60–90s |
| Reef2Reef / Forum | 1920×1080 | 5–15 min |

## Related Skills

- `wildlife-video-maker` — Outdoor aquatic and ocean content
- `tiktok-content-maker` — Short aquarium clips for social media
- `tutorial-video-creator` — Educational fishkeeping how-to content

## Common Questions

**Can I show water chemistry parameter changes over time?**
Set `show_parameters: true` and describe your parameter history in the prompt. NemoVideo creates a timeline overlay showing how your parameters evolved.

**What frame rate works best for flowing coral polyps?**
Mention "60fps" or "slow motion for polyp extension" in the prompt. High frame rate captures the meditative movement of soft coral and anemone tentacles.

**Can I create content for multiple tanks in one video?**
Yes — describe each tank in sequence for a fish room tour. Set `content_style: "fish_room"` for multi-tank content with consistent visual transitions between setups.
