# Agave Korean implementation record

- Owner: Codex /root, single executor; no delegated agents.
- Workspace: `/Users/jhkim/dev/moeng.dev/agave-korean`; initially empty, not a Git repository.
- Authorization: implement, download official sources, build locally, verify and generate preview. No publishing or font installation requested.
- Status: complete — implementation, real builds, automated verification, preview generation and documented self-review finished.
- Goal: preserve normal Agave Regular/Bold outlines, metrics and hinting; append Korean with exact 2-cell advance; configurable sources and transformations; working local preview and automated verification.

## Plan / writable scopes

1. Research official releases/licenses and inspect tables (`docs/`, `.cache/`, dependency files). Verify exact non-variant Agave assets and Sarasa structure.
2. Implement acquisition/config and selective glyph import (`builder/`, `sources/`, `build.sh`). Preserve Agave glyph IDs; decompose only imported glyphs; separate uniform scale from advance. Validate actual output.
3. Add static comparison preview and documentation (`preview/`, `README.md`, `docs/`, `fonts/local/`). Verify browser loading, Regular/Bold, sizes and cell alignment.
4. Run regression tests and end-to-end builds with Sarasa and alternative sources (`tests/`, ignored `build/`). Self-review, record evidence and remaining constraints.

## Research

- GitHub API: Agave tag 39, exact `Agave-Regular.ttf` and `Agave-Bold.ttf` (variant assets are separate).
- GitHub API: Sarasa v1.0.41, `SarasaMonoK-TTF-Unhinted-1.0.41.7z`, SHA256 `13803f1209ceb8aa55dee60d7b28975fd05b6fdf815411320db8f4ecaa27ec61`.
- OFL 1.1 confirmed for Agave, Sarasa, Source Han Sans, Noto Sans KR, Pretendard, D2Coding. Source/Pretendard/D2Coding reserved names require distinct derivative family names.
- Sandbox network DNS unavailable; explicitly escalated official-source downloads work. No automatic approval rejection.

## Verification / remaining

- Implemented JSON presets, cache/download/local/archive handling, selective glyf append, validation, CLI, static preview and docs.
- All five presets built successfully (10 TTFs): Sarasa/Han/Noto/D2 11266 Korean characters, Pretendard 11225.
- Agave original raw glyph blocks EXACT equality: Regular 2487/2487, Bold 743/743; hint tables and hmtx preserved.
- 11 unittest tests passed, including full real-font shaping across 10 outputs and all 11172 NFC/NFD syllables.
- Rendered and visually inspected Sarasa Regular/Bold, Source Han Regular and Pretendard Bold with hb-view at 18px.
- Browser verification limitation: CUA reported no browser; native Safari attempt failed because computer-use service could not start. No direct browser visual result claimed.
- Corrected donor coverage requirement after Pretendard lacked 41 archaic compatibility characters: modern Hangul mandatory, other compatibility characters imported when present.
- D2 1.3.2 ZIP/tag lacks license file; embedded font name table explicitly identifies OFL. Bundle official OFL text from pinned current repository commit, retain binary copyright as well.
- All font/archive/license downloads now have pinned SHA-256; checksum-verified final offline --all build passed (10 TTFs).
- Final suite: 15 tests passed in 6.165s. FreeType-hinted ASCII PNGs exactly match original Agave at 12/14/16/18px for both weights.
- Preview DOM success/failure simulations passed for 5 sources/10 weights; file references valid. This is not real-browser verification.
- No-argument `./build.sh` passed and Sarasa rebuild SHA-256 matched before/after for both weights.
- Self-review PASS bound to 25-file SHA-256 `152f02a7d48cb8cf348eddbf51854c4b0fb39d157df73befc011f285391f2fee`; scope and complete evidence in `docs/verification.md`.
- Fixed local fsType mode preservation, per-source config failure isolation, and invalid redistribution metadata during self-review. No unresolved implementation blockers.
- No code commits (workspace is not a Git repository), external publishing, installed fonts, live executor handoffs or scheduled wake-ups. Existing user edits: none at start.
- Remaining limitations are intentional: unhinted Korean, modern Hangul/compatibility coverage, no Nerd Font/Italic/old Hangul layout. Browser visual QA unavailable due host capability failure; documented, not claimed as passed.
