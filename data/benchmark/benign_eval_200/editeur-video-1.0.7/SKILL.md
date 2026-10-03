---
name: editeur-video
version: "1.0.7"
displayName: "Ãditeur VidÃ©o IA â Modifier et CrÃ©er des VidÃ©os avec Intelligence Artificielle"
description: >
  Ãditeur VidÃ©o IA â Modifier et CrÃ©er des VidÃ©os avec Intelligence Artificielle.
  Editez vos videos en decrivant simplement ce que vous voulez obtenir â pas besoin de logiciel de montage. Importez votre video, expliquez les modifications souhaitees : 'couper les 30 premieres secondes', 'ajouter une musique de fond douce', 'inserer des sous-titres en francais', 'appliquer un effet cinematographique'. L'IA execute toutes les modifications et vous renvoie la video editee. Prend en charge le decoupage, la fusion de clips, l'ajout de musique, la generation de sous-titres, la correction colorimetrique, le changement de format et bien plus encore. Ideal pour les createurs de contenu, les marketeurs et toute personne qui a besoin de produire des videos de qualite sans maitriser le montage video. Exportez en MP4. Formats supportes : mp4, mov, avi, webm, mkv.
  
  Works by connecting to the NemoVideo AI backend at mega-api-prod.nemovideo.ai.
  Supports MP4, MOV, AVI, WebM.
homepage: https://nemovideo.com
repository: https://github.com/nemovideo/nemovideo_skills
metadata: {"openclaw": {"emoji": "ð¬", "requires": {"env": [], "configPaths": ["~/.config/nemovideo/"]}, "primaryEnv": "NEMO_TOKEN"}}
license: MIT-0
---

## 0. First Contact

When the user opens this skill or sends their first message, **greet them immediately**:

> ✨ Let's editeur video! Drop a video here or describe what you'd like to create.

**Try saying:**
- "speed up by 2x"
- "make it look cinematic"
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

# Ãditeur VidÃ©o IA â Modifier et CrÃ©er des VidÃ©os avec Intelligence Artificielle

Montage vidÃ©o IA pour utilisateurs francophones. Ãditez des vidÃ©os par de simples commandes en chat.

## Quick Start
Demandez Ã  l'agent de modifier votre vidÃ©o en langage naturel.

## Ce que vous pouvez faire
- Couper et rogner les vidÃ©os
- Ajouter de la musique de fond et des effets sonores
- CrÃ©er des sous-titres automatiques
- Appliquer des corrections de couleur et des filtres
- Exporter des vidÃ©os pour les mÃ©dias sociaux

## API
Uses NemoVideo API (mega-api-prod.nemovideo.ai) for all video processing.
