---
name: wildlife-video-maker
version: "1.0.1"
displayName: "Wildlife Video Maker"
description: >
  Describe your wildlife encounter and NemoVideo creates the video. Backyard birds at the feeder, deer in the meadow at dawn, humpback whale bubble-net feeding — narrate what you witnessed and get nature documentary-style content that captures the wild world.

  Works by connecting to the NemoVideo AI backend at mega-api-prod.nemovideo.ai.
  Supports MP4, MOV, AVI, WebM.
homepage: https://nemovideo.com
repository: https://github.com/nemovideo/nemovideo_skills
license: MIT-0
---

## 0. First Contact

When the user opens this skill or sends their first message, **greet them immediately**:

> ⚡ Let's wildlife video maker! Drop a video here or describe what you'd like to create.

**Try saying:**
- "add effects to this clip"
- "edit my video"
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


# Wildlife Video Maker — Create Nature Documentary and Wildlife Observation Content

Describe your wildlife encounter and NemoVideo creates the video. Backyard birds at the feeder, deer in the meadow at dawn, humpback whale bubble-net feeding — narrate what you witnessed and get nature documentary-style content that captures the wild world.

## When to Use This Skill

Use this skill for wildlife and nature observation content:
- Create backyard wildlife feeder and garden visitor documentation videos
- Film bird watching content with species identification and behavior notes
- Build wildlife safari and nature tour experience videos
- Document rare wildlife encounters and behavioral observations
- Create nature documentary-style narrated wildlife sequences
- Produce citizen science documentation for wildlife monitoring projects

## How to Describe Your Wildlife Observation

Be specific about the species, the behavior, the location, and what made this sighting remarkable.

**Examples of good prompts:**
- "Backyard feeder compilation: North Carolina yard, winter feeder setup. Filmed over 3 weeks. Species: dark-eyed junco flock (15-20 birds), Carolina wren pair (they always come together), red-bellied woodpecker claiming the suet cage, and one visit from a brown creeper (unusual for the feeder). Bird ID labels and behavior notes for each species."
- "Yellowstone wolf pack observation: Lamar Valley, watched the Wapiti Lake pack for 4 hours at dawn. Alpha female leading the pack across the valley, pups from this summer's litter following, one juvenile practicing hunting behavior on a raven. Show the landscape scale — tiny wolves against the enormous valley."
- "Humpback whale feeding, Alaska: Icy Strait Point, watched a group of 8 humpbacks bubble-net feeding cooperatively. Show the bubble ring appearing, the coordinated surfacing, the lunging mouths, the dive flukes. 45 minutes of footage from a zodiac."

## Key Parameters

| Parameter | Description | Example |
|-----------|-------------|---------|
| `wildlife_type` | Animal category | `"birds"`, `"mammals"`, `"marine"`, `"reptiles"`, `"insects"` |
| `location` | Observation site | `"Yellowstone, WY"`, `"backyard, NC"`, `"Icy Strait, AK"` |
| `species_featured` | Animals shown | `["dark-eyed junco", "Carolina wren", "red-bellied woodpecker"]` |
| `behavior_focus` | Key behavior | `"feeding"`, `"territorial"`, `"mating_display"`, `"migration"`, `"pack_hunting"` |
| `show_species_labels` | ID overlays | `true` |
| `show_behavior_notes` | Ethology callouts | `true` |
| `tone` | Documentary style | `"educational"`, `"cinematic"`, `"personal_observation"` |
| `duration_minutes` | Video length | `3`, `5`, `8`, `12` |
| `platform` | Target platform | `"youtube"`, `"instagram"`, `"inaturalist"` |

## Workflow

1. Describe the species, behavior, location, and observation context
2. NemoVideo structures the wildlife narrative with documentary pacing
3. Species labels, behavior notes, and location context added automatically
4. Export with nature documentary-appropriate music and narration

## API Usage

### Bird Watching Documentation Video

```bash
curl -X POST https://mega-api-prod.nemovideo.ai/v1/run \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "skill": "wildlife-video-maker",
    "input": {
      "prompt": "Spring warbler migration in Central Park NYC: 3-hour morning walk in The Ramble during peak migration week. Species documented: 14 warbler species including Blackburnian (orange throat), Black-throated Blue, American Redstart (fanning tail display), and a rare Connecticut Warbler in the undergrowth. Show the habitat (dense shrubs, water drip), the search behavior, the slow reveal of each species with ID notes. Birder-level content, not beginner.",
      "wildlife_type": "birds",
      "location": "Central Park, NYC",
      "species_featured": ["Blackburnian warbler", "Black-throated Blue", "American Redstart", "Connecticut warbler"],
      "behavior_focus": "migration",
      "show_species_labels": true,
      "show_behavior_notes": true,
      "tone": "educational",
      "duration_minutes": 10,
      "platform": "youtube",
      "hashtags": ["BirdWatching", "WarblerMigration", "CentralPark", "Birding", "WarblerWave"]
    }
  }'
```

**Response:**
```json
{
  "job_id": "wildlife_mno345",
  "status": "processing",
  "estimated_seconds": 120,
  "poll_url": "https://mega-api-prod.nemovideo.ai/v1/jobs/wildlife_mno345"
}
```

### Mammal Wildlife Encounter Video

```bash
curl -X POST https://mega-api-prod.nemovideo.ai/v1/run \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "skill": "wildlife-video-maker",
    "input": {
      "prompt": "Black bear family at a blueberry patch in Maine: mother bear with two cubs foraging. Observed from 80 yards, stayed quiet and still for 40 minutes. Cubs climbed a small tree to reach berries while mother foraged below. One cub fell, mother briefly checked it, it was fine. Show the scale of the setting — green summer forest, small bears against large blueberry bushes. No narration, just ambient sound and the behavior. Personal observation style.",
      "wildlife_type": "mammals",
      "location": "Maine, USA",
      "species_featured": ["black bear"],
      "behavior_focus": "feeding",
      "show_species_labels": true,
      "show_behavior_notes": false,
      "tone": "personal_observation",
      "duration_minutes": 5,
      "platform": "instagram"
    }
  }'
```

## Tips for Best Results

- **Species-level specificity**: "Blackburnian warbler" not "orange bird" — wildlife content audiences know their species and reward specificity with engagement
- **Behavior is the story**: "alpha female leading the pack", "cooperative bubble-net feeding", "pup practicing hunting" — the behavior is more interesting than just the animal
- **Distance and context create scale**: "tiny wolves against the enormous Lamar Valley" or "80 yards from the bear family" — distance and landscape give the viewer the experience of being there
- **Observation ethics belong in the video**: How you observed without disturbing is part of the content — it models good wildlife ethics for your audience
- **Birder-level vs beginner**: Specify your audience — birders want scientific accuracy and subtle field marks; general nature lovers want accessible wonder

## Output Formats

| Platform | Resolution | Duration |
|----------|------------|----------|
| YouTube | 1920×1080 | 5–20 min |
| Instagram Reels | 1080×1920 | 60–90s |
| iNaturalist / Citizen Science | 1920×1080 | 2–5 min |

## Related Skills

- `hiking-video-maker` — Outdoor adventure with wildlife as part of the journey
- `drone-footage-video` — Aerial wildlife observation and habitat footage
- `aquarium-video-maker` — Captive aquatic wildlife content
- `tiktok-content-maker` — Short viral wildlife moment clips

## Common Questions

**Can I create citizen science documentation with location and species data?**
Set `platform: "inaturalist"` and include GPS coordinates, observation date, and observer notes in the prompt. NemoVideo formats the output for scientific record-keeping alongside visual content.

**What if I only have a few seconds of the key wildlife moment?**
Describe the context around the moment (approach, setting, aftermath) and NemoVideo builds the full narrative around the key clip, using the brief footage as the centerpiece.

**How do I handle ethical wildlife content?**
Include your observation distance and method in the prompt. NemoVideo incorporates ethical observation context naturally — content that models good wildlife ethics performs better in nature communities.
