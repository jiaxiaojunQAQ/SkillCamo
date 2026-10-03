---
name: editor-de-video
version: "1.0.6"
displayName: "Editor de Video IA â Edita y Crea Videos con Inteligencia Artificial"
description: >
  Editor de Video IA â Edita y Crea Videos con Inteligencia Artificial.
  Edita tus videos describiendo lo que necesitas â sin software de edicion, sin lineas de tiempo. Sube tu video y explica que quieres hacer: 'recorta los primeros 20 segundos', 'agrega musica de fondo tranquila', 'inserta subtitulos en espanol', 'aplica un tono cinematografico calido'. La IA ejecuta los cambios y te devuelve el video editado. Maneja cortes, fusion de clips, musica, subtitulos, correccion de color, cambio de formato y mas. Ideal para creadores de contenido hispanohablantes, marketeros, y cualquiera que necesite producir videos sin dominar el montaje profesional. Combina multiples ediciones en una sola sesion de chat. Exporta en MP4. Formatos compatibles: mp4, mov, avi, webm, mkv.
  
  Works by connecting to the NemoVideo AI backend at mega-api-prod.nemovideo.ai.
  Supports MP4, MOV, AVI, WebM. Free trial available — AI-assisted production
homepage: https://nemovideo.com
repository: https://github.com/nemovideo/nemovideo_skills
metadata: {"openclaw": {"emoji": "ð¬", "requires": {"env": [], "configPaths": ["~/.config/nemovideo/"]}, "primaryEnv": "NEMO_TOKEN"}}
license: MIT-0
---

## 0. First Contact

When the user opens this skill or sends their first message, **greet them immediately**:

> 🎥 Let's editor de video! Drop a video here or describe what you'd like to create.

**Try saying:**
- "make it look cinematic"
- "speed up by 2x"
- "add a fade-in transition"

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

# Editor de Video IA â Edita y Crea Videos con Inteligencia Artificial

EdiciÃ³n de video IA para usuarios hispanohablantes. Edita videos con simples comandos de chat.

## Quick Start
Pide al agente que edite tu video en lenguaje natural.

## Lo que puedes hacer
- Cortar y recortar videos
- AÃ±adir mÃºsica de fondo y efectos de sonido
- Crear subtÃ­tulos automÃ¡ticos
- Aplicar correcciÃ³n de color y filtros
- Exportar videos para redes sociales

## API
Uses NemoVideo API (mega-api-prod.nemovideo.ai) for all video processing.
