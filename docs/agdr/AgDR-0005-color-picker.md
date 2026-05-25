# Color picker for config colours (react-colorful + ASS⟷RGBA conversion)

> In the context of the schema-driven Config editor (`web/src/components/ConfigEditor.tsx`), facing the need to let users pick caption colours visually instead of typing raw ASS codes like `&H00FFFFFF`, I decided to add **react-colorful** as the picker and a **pure `assColor.ts` conversion utility** for the ASS⟷RGBA mapping, to achieve an accessible alpha-capable picker that round-trips ASS values correctly, accepting a new (tiny, zero-dep) frontend dependency.

## Context

Caption colours live in `config.yaml` in **ASS subtitle format `&HAABBGGRR`** (see `CaptionsConfig` in `src/reels/infrastructure/config/settings.py`: `base_color`, `active_color`, `box_color`). The format has two non-obvious properties:

1. **Byte order is reversed** vs RGB — it is `BB GG RR`, not `RR GG BB`.
2. **The `AA` byte is TRANSPARENCY, not opacity** — `00` = fully opaque, `FF` = fully transparent (inverted from normal alpha).

`box_color = &H90000000` is a translucent black box, so the picker **must** support an alpha channel. A native `<input type="color">` does not support alpha, ruling it out.

Two decisions are recorded here: the picker library, and the conversion approach.

## Options Considered

### Picker library

| Option | Pros | Cons |
|--------|------|------|
| **react-colorful** | Tiny (~2.8 kB), zero deps, MIT, `RgbaColorPicker` supports alpha, accessible, React 19 compatible | One more dependency |
| Native `<input type="color">` | No dependency | **No alpha support** — can't represent `box_color`; non-standard popover UX |
| react-color | Familiar API | Large, heavier dep tree, less actively maintained |
| Build a custom picker | No dependency | Reinventing hue/saturation/alpha + accessibility is high-effort and bug-prone |

### Conversion approach

| Option | Pros | Cons |
|--------|------|------|
| **Pure `assColor.ts` util (`assToRgba` / `rgbaToAss`)** | Testable in isolation, single source of truth, doc-comment examples, robust to prefix casing + 6/8-digit | Must hand-handle byte reversal + alpha inversion |
| Inline conversion in the component | Less indirection | Untestable, easy to get the reversal/inversion wrong, not reusable |

## Decision

Chosen: **react-colorful (`RgbaColorPicker`)** for the picker, surfaced through a Radix `Popover` (already a project dependency) for accessible, keyboard-usable, outside-click/Esc-closing behaviour; and a **pure `web/src/lib/assColor.ts`** module for all ASS⟷RGBA conversion.

The conversion exposes `a` as standard **opacity** (0 = transparent, 1 = opaque) and inverts to/from ASS transparency on both directions, while reversing the colour byte order. The picker speaks RGBA; only `assColor.ts` knows about the ASS quirks, so the value written back on save stays valid ASS and the libass renderer is unchanged.

Color fields are detected **generically** by name (`key.endsWith("_color")`) so future colour settings get the picker automatically.

## Consequences

- New runtime dependency `react-colorful@^5.7.0` (MIT, zero transitive deps).
- ASS-format knowledge is centralised in one tested-by-example module; the picker and any future consumer reuse it.
- Round-trip verified on the real config values: `&H00FFFFFF` → opaque white → back exactly; `&H0000D7FF` → r255 g215 b0 → back exactly; `&H90000000` → opacity ≈0.435 → back exactly. White does not become black; alpha does not flip.
- **Follow-up:** the repo has no JS test harness (no vitest/jest). The conversion util is documented with examples and verified via a one-off `npx tsx` round-trip, but a real FE test harness (vitest) should be stood up so `assColor.ts` gets committed unit tests covering byte-reversal + alpha-inversion edge cases. Out of scope for this PR.

## Artifacts

- `web/src/lib/assColor.ts` — conversion utility
- `web/src/components/ColorField.tsx` — swatch + popover picker + synced raw input
- `web/src/components/ConfigEditor.tsx` — generic `_color` detection wiring
- Ticket: https://github.com/hibrahem/reels-generator/issues/26
