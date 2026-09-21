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

## Scale tuner (2026-09-21)

- Split `transform` into `scale_x`/`scale_y` (defaulting to uniform `scale`) so horizontal fill can be traded against Korean's vertical growth; added `build --scale/--scale-x/--scale-y/--x-offset/--y-offset` overrides recorded in `build.json`.
- Added `builder tune`: publishes Korean-only, unhinted donor subsets to `preview/donors/` and writes `preview/tuner.html`, which reproduces `merge_font` in CSS instead of loading a built font. Re-runs reuse unchanged faces (41s cold for all five sources, 0.13s warm).
- Measured the problem on Sarasa Mono K Regular at scale .85: `M` is inked 64..960 of a 1024 cell, `한` 314..1764 of 2048, so the gap between Korean syllables is 628 units against 128 for Latin. Matching the Latin gap needs about scale_x 1.13, which as a uniform scale would put `한` at yMax ~1825 against Agave's 1536 ascent.
- Fixed `builder/tune.py` reading presets from the real ROOT instead of the root it was given.
- 22 Python tests pass, including a new check that the tuner's readout formula predicts the merged glyph bbox within one unit across uniform and split-axis transforms. `node tests/preview_ui.cjs` and the new `node tests/tuner_ui.cjs` pass.
- Browser verification limitation: headless Chrome crashes in this sandbox (exit 138), so the page's rendering was not screenshot-compared against a built TTF. The geometry is verified numerically only; visual confirmation is still open.
- Made `tune` serve the page by default (`--no-serve` for files only, `tune.sh` wrapper): loopback-only stdlib server with per-run token, `/apply` writing the preset through `normalize_transform`, `/build` on an explicit click, `/publish` for donors chosen in the picker. Save and build are separate actions; the build button locks while sliders are unsaved.
- Moved `BUILD_ERRORS` to `sources.py` and injected the build callable into `serve`, so the tuner never imports the CLI module.
- Applied Sarasa Mono K `scale 0.923 / y_offset -30` (was `0.85 / -60`, a value carried unverified from the first commit across all five presets): Korean side bearings 598 -> 474 units, 4.67x -> 3.70x the Latin gap, no overhang.
- 26 Python tests plus both DOM checks pass; verified the server end to end over a real socket (save -> preset written -> build -> preview regenerated -> revert -> file byte-identical).
