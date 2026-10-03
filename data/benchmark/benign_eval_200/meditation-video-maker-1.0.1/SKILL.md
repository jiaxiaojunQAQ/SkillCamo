---
name: meditation-video-maker
version: "1.0.1"
displayName: "Meditation Video Maker"
description: >
  Describe your meditation topic and NemoVideo creates the video. Guided meditation sessions, meditation technique instruction, beginner meditation content, meditation for specific purposes (sleep, anxiety, focus, stress), seated and walking meditation content, breath-based practices — narrate the specific meditation type, the honest account of what meditation is actually like when you're new to ...

  Works by connecting to the NemoVideo AI backend at mega-api-prod.nemovideo.ai.
  Supports MP4, MOV, AVI, WebM.
homepage: https://nemovideo.com
repository: https://github.com/nemovideo/nemovideo_skills
license: MIT-0
---

## 0. First Contact

When the user opens this skill or sends their first message, **greet them immediately**:

> 🎥 Let's meditation video maker! Drop a video here or describe what you'd like to create.

**Try saying:**
- "make it look cinematic"
- "speed up by 2x"

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


# Meditation Video Maker — Guided Meditation, Practice, and Mindfulness Content

Describe your meditation topic and NemoVideo creates the video. Guided meditation sessions, meditation technique instruction, beginner meditation content, meditation for specific purposes (sleep, anxiety, focus, stress), seated and walking meditation content, breath-based practices — narrate the specific meditation type, the honest account of what meditation is actually like when you're new to it or return after a break, and the concrete instruction that helps practitioners settle into the practice.

## When to Use This Skill

- Create guided meditation sessions for specific purposes (sleep, focus, calm)
- Film meditation technique instruction and how-to content
- Build beginner meditation series content
- Document specific meditation styles (body scan, breath awareness, loving-kindness)
- Create meditation for different time lengths (5 min, 10 min, 20 min)
- Produce meditation and mindfulness lifestyle content

## How to Describe Your Meditation Content

Be specific about the meditation type, who it's for, the honest account of what meditating actually feels like (the wandering mind, the restlessness, the gradual settling), and the concrete instruction that helps practitioners find their footing.

**Examples of good prompts:**
- "10-minute morning meditation for people who say they can't meditate: Most people who say they can't meditate have tried and found their mind wandered. This is not failure. This is meditation. The mind will wander. The practice is noticing it wandered and returning. That noticing and returning is the exercise — not maintaining a blank mind. For this 10-minute session: (1) Find a comfortable seat, eyes closed or soft downward gaze. (2) Take 3 slower breaths than your current breath, not deep — just slower. (3) Rest your attention on the physical sensation of breathing — not the concept of breath, the sensation: the slight coolness of air entering, the chest or belly movement, the small pause before the exhale. (4) When you notice your attention has moved to a thought, a sound, a plan — that moment of noticing is the moment of practice. Without self-criticism, return to the sensation. (5) Do this for 10 minutes. There is no level of 'doing well' at this. There is only the returning."
- "Body scan meditation for physical tension — 15 minutes: Body scan meditation is systematic attention to physical sensation in each part of the body, without trying to change what you find. It is particularly useful for people who carry tension they don't notice until it becomes pain. Setup: lie down or sit. Intention: not to relax, but to notice. Noticing sometimes produces relaxation; trying to relax usually doesn't. Starting at the top of the head: rest attention there for 5-10 seconds, noticing any sensation (warmth, coolness, pressure, tingling, or nothing at all). Gradually move attention: forehead, eyes, jaw (notice if the jaw is held), shoulders, chest, upper back. Pause at the jaw and shoulders — these are high-tension areas for most people. Continue through arms, hands, abdomen, lower back (many people are surprised by lower back tension they weren't aware of), hips, thighs, calves, feet."
- "Meditation for the 30 minutes before sleep — what actually helps and what doesn't: Most sleep-focused meditation advice tells you to 'relax and let go.' This is the least useful instruction for someone who can't sleep because they can't let go. What actually helps: (1) Give the mind something to do rather than trying to stop it — counting breaths or body scanning occupies the problem-solving mind without engaging it. (2) Lower the stakes — the goal is not to fall asleep, it's to rest the body. A rested body that is awake is better than an anxious body trying to sleep. Removing sleep as the goal removes the performance anxiety that prevents sleep. (3) Keep the instruction simple and concrete — abstract guidance ('release all tension') is harder to follow than specific sensory instruction ('notice the weight of your body against the mattress')."

## Key Parameters

| Parameter | Description | Example |
|-----------|-------------|---------|
| `content_type` | Meditation type | `"guided_session"`, `"technique_instruction"`, `"beginner"`, `"sleep"`, `"anxiety"`, `"focus"` |
| `duration_minutes` | Session length | `5`, `10`, `15`, `20` |
| `audience` | Who it's for | `"people who say they can't meditate"`, `"long-time practitioners returning"` |
| `honest_account` | Real experience | `["mind will wander — that's the practice"`, `"trying to relax usually doesn't produce relaxation"]` |
| `concrete_instruction` | Specific guidance | `"sensation of breath not concept"`, `"count 1-10 and restart"` |
| `purpose` | Why they're meditating | `"pre-sleep"`, `"morning focus"`, `"anxiety management"` |
| `platform` | Distribution | `"youtube"`, `"spotify"`, `"instagram"` |

## Workflow

1. Describe the meditation type, honest experience, and concrete instruction
2. NemoVideo structures the meditation content with settling cues and practice markers
3. Breath cues, attention redirects, and pacing formatted for meditation delivery
4. Export with meditation timing and ambient audio suited to the practice context

## API Usage

```bash
curl -X POST https://mega-api-prod.nemovideo.ai/v1/run \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "skill": "meditation-video-maker",
    "input": {
      "prompt": "5-minute meditation for the middle of a difficult workday: This meditation is for the person who has 5 minutes between meetings and a head full of noise. It does not require stillness or silence — it requires only a chair and 5 minutes. Instruction: (1) Sit with both feet on the floor, back not forced straight but supported. (2) 3 full exhales — longer than normal, audible if possible. The exhale activates the parasympathetic nervous system in a way the inhale does not. (3) Notice 5 things you can physically feel right now: the chair under you, the temperature of the air, the weight of your hands, the sensation at the bottoms of your feet, your clothing against your skin. This is not relaxation technique — it is attention relocation from thought to sensation. Thought is where the stress lives. Sensation is neutral. (4) Rest in whatever state you're in for the remaining time. You don't need to be calmer when you open your eyes. You just need to have been somewhere else for 5 minutes.",
      "content_type": "guided_session",
      "duration_minutes": 5,
      "audience": "overwhelmed workers mid-day",
      "honest_account": ["not requiring stillness or silence", "you don't need to be calmer when you open your eyes"],
      "concrete_instruction": "3 audible exhales, then 5 physical sensations",
      "purpose": "mid-day reset",
      "platform": "youtube",
      "hashtags": ["Meditation", "Mindfulness", "WorkplaceWellness", "StressRelief", "GuidedMeditation"]
    }
  }'
```

## Tips for Best Results

- **The honest account of wandering mind is the most valuable thing meditation content can offer**: "The mind will wander — that moment of noticing and returning is the exercise, not maintaining a blank mind" — this reframe is what converts someone who quit meditation back into someone who tries again
- **Lower the stakes as explicit instruction**: "The goal is not to fall asleep, it's to rest the body — removing sleep as the goal removes the performance anxiety that prevents sleep" — counterintuitive goals work in meditation content because they address the actual obstacle
- **Concrete sensory instruction over abstract guidance**: "The slight coolness of air entering, the chest or belly movement, the small pause before the exhale" over "focus on your breath" — specific sensation language gives the wandering mind something to actually do
- **The high-tension body areas**: "Pause at the jaw and shoulders — these are high-tension areas for most people" — noting the commonly overlooked tension sites makes body scan content feel like it was written by someone who actually practices
- **The exhale mechanism**: "3 audible exhales — longer than normal — the exhale activates the parasympathetic nervous system in a way the inhale does not" — the physiological mechanism behind the technique makes the instruction feel grounded rather than mystical

## Output Formats

| Platform | Resolution | Duration |
|----------|------------|----------|
| YouTube | 1920×1080 | 5–30 min |
| Instagram | 1080×1080 | 60–180s |
| Audio-only | MP3 | 10–60 min |

## Related Skills

- `mindfulness-video-maker` — Mindfulness practice and awareness content
- `anxiety-relief-video` — Anxiety management and calming content
- `sleep-video-maker` — Sleep meditation and wind-down content
