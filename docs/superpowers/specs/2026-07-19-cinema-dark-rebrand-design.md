# Cinema Dark rebrand — Reels Studio web app

**Date:** 2026-07-19 · **Status:** Approved (user picked "Cinema Dark" + "Full UI/UX pass", then "Approve — go build it") · **Beads:** rg-hoj

## Goal

Replace the bolted-on indigo-over-grayscale look with a coherent brand ("Cinema Dark")
and fix the UX debt found in a full screen-by-screen review. Presentation layer only:
no API, data-flow, or behavior changes.

## Brand system

- **Surfaces:** warm near-black ("screening room") — background `oklch(0.155 0.008 70)`,
  card `oklch(0.205 0.008 70)`, subtle warm borders. Dark-only; no light theme.
- **Accent:** amber/gold `oklch(0.78 0.14 75)` (record-light / film-leader gold) with a
  dark amber foreground on primary buttons. Ring/focus = amber. Emerald = success,
  red = destructive. Everything flows through the shadcn token layer in `web/src/index.css`.
- **Type:** headings `Space Grotesk Variable` (`--font-heading`), body stays
  `Geist Variable`. Add `@fontsource-variable/space-grotesk`.
- **Logomark:** inline SVG — a 9:16 rounded frame with a play notch, amber on dark —
  replaces the 🎬 emoji in the header, Library placeholder tiles, and the favicon
  (SVG data-URI in `index.html`).

## UX restructure (per screen)

1. **Shell (`App.tsx`):** logomark + wordmark; nav gets icons + proper labels
   (Library, Gallery, Silence, Config, Health) with an amber active underline;
   "N running" pill stays, restyled amber.
2. **Library / VideoCard:** duration badge overlaid on the thumbnail; the row of 9
   stage chips becomes a slim **stage progress bar** + "n/9 stages" label
   (title attr lists stage names). Meta line tightened.
3. **Video detail:** pipeline controls become a labeled toolbar card ("Pipeline",
   from → to selects with visible labels); player + timeline visually unified in one
   framed block; reels panel cards drop the chip soup for the same progress bar;
   Delete demoted to an icon-only ghost button.
4. **Reel editor (`ReelDetail`):** sectioned cards with headings — Preview, Trim,
   Transcript, Pipeline. Stage list becomes a numbered step list with explicit
   "Re-run stage" / "Re-run from here" labels.
5. **Gallery:** poster-first — no always-on `<video controls>` grid; card shows the
   poster (metadata preload, no controls) with a play overlay; click to play inline.
   Download + Open video actions kept.
6. **Silence Remover:** framed dropzone restyled to brand, labeled fields kept.
7. **Config:** groups become titled cards with the section description; sticky Save
   bar appears only when the form is dirty.
8. **Health (`Doctor`):** pass/fail icons (check/alert), failing rows get an amber
   hint line where the API provides detail.
9. **Shared:** one `EmptyState` component (icon, message, optional action) and one
   skeleton/error pattern reused by Library, Gallery, Doctor, transcript panel.

## Non-goals

- No light theme, no routing changes, no new dependencies beyond the heading font,
  no backend/API changes, no copy rewrites beyond label casing/clarity.

## Testing

Visual verification in the browser across all 5 tabs + video detail + reel editor
with real library data; `npm run build` must pass.
