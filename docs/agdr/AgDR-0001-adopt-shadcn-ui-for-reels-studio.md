---
id: AgDR-0001
timestamp: 2026-05-24T23:25:00Z
agent: claude
model: claude-opus-4-7[1m]
trigger: user-prompt
status: executed
---

# Adopt shadcn/ui for the Reels Studio UI revamp

> In the context of revamping the Reels Studio web UI to a polished, SaaS-grade look, facing a choice of component-library foundation under a "free / no-paid-tools" constraint with an existing Tailwind 4 + Vite 6 + React 19 stack, I decided to adopt **shadcn/ui** (Radix primitives + Tailwind, copy-in components) to achieve a polished, accessible, themeable UI without a second styling system or runtime lock-in, accepting that the components are owned and maintained in-repo (copy-paste, not a versioned package).

## Context

- Existing `web/` stack: React 19, Vite 6, **Tailwind CSS 4**, TanStack Query. No component library today; styling is hand-rolled Tailwind.
- Validation of the revamp idea (`reels-generator#4`, Q5) set a **free/OSS constraint** — "don't pay money now; if a good free option exists use it, otherwise build." The product's differentiation is the pipeline, not the UI chrome.
- Target surfaces include interactive widgets that need accessible primitives: the pipeline runner, the config editor forms, dialogs, and the gallery.

## Options Considered

| Option | Pros | Cons |
|--------|------|------|
| **shadcn/ui** (Radix + Tailwind, copy-in) | Free/MIT; Tailwind-4 native (no 2nd styling system); you own the code (no upgrade treadmill / lock-in); Radix = accessible interactive primitives; themeable via CSS variables | Components copied into the repo (you maintain them); some assembly required; not a one-import package |
| **Mantine** (full MIT component lib) | Batteries-included; large component set; strong DX; React 19 support | Ships its own styling system that runs in parallel with the existing Tailwind 4 (paradigm duplication); heavier runtime; brand restyling is more work |
| **DaisyUI** (Tailwind plugin, CSS-only) | Free/MIT; pure Tailwind classes; tiny; zero JS | Too shallow for complex interactive widgets (no accessible combobox/dialog primitives); would still need Radix/Headless for the hard parts |
| Tailwind Plus / Tailwind UI (excluded) | High-quality templates | **Paid** — violates the free-only constraint |

## Decision

Chosen: **shadcn/ui**, because it is the only option that builds on the Tailwind 4 already present in the repo (avoiding a second, competing styling system), it is free/MIT, it provides accessible Radix primitives for the interactive surfaces, and it avoids runtime and version lock-in by living as owned code under `web/src/components/ui/`.

## Consequences

- Add Radix UI peer dependencies + the shadcn CLI; initialise `components.json` against Tailwind 4 + Vite.
- Establish brand **design tokens** as CSS variables and theme components centrally (this is where "polished SaaS" actually comes from — not the component library alone).
- Generated components live in `web/src/components/ui/` and are maintained in-repo; normal PR review covers them.
- No paid dependency. Revisit only if a required primitive is missing — then pull in Radix or Headless UI directly rather than switching libraries.
- Pairs with the parked "Bet A" scope from the validation: restyle the core flow first — landing → trigger job → live progress → gallery.

## Artifacts

- Idea: `reels-generator#4`
- Validation: `projects/reels-generator/validation/issue-4-saas-ui-revamp-validation.md` (ApexYard ops portfolio)
- Implementation commit / PR: _TBD_
