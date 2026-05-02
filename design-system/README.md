# ZARIS Design System

> **Design for web apps de ZARIS**
> A warm-minimalist design system in the spirit of a code-editor editorial publication — cream canvas, warm near-black ink, oklab borders, and a three-voice typographic system.

---

## Index / Manifest

| File | What it is |
|---|---|
| `README.md` | This file — brand context, content, visual foundations, iconography, index |
| `colors_and_type.css` | All CSS variables + semantic classes for color, type, radius, spacing, shadow |
| `fonts/fonts.css` | Font stack declarations |
| `SKILL.md` | Skill manifest for Claude Code compatibility |
| `assets/` | Logos, icons, illustrations, imagery |
| `preview/` | Small HTML cards that populate the Design System tab |
| `ui_kits/web-app/` | ZARIS web app UI kit (React/JSX components + interactive index.html) |
| `ui_kits/marketing-site/` | ZARIS marketing site UI kit (hero, features, pricing, nav, footer) |

---

## 1. Brand Context

ZARIS is a platform of **design tools for web apps** — we build the surfaces that other makers build with. The brand voice is that of a premium print publication that happens to be software: warm, precise, literary, unafraid of white space, deeply opinionated about type.

The aesthetic is **warm minimalism meets code-editor elegance**: not stark, not clinical, not neon. Everything sits on a cream canvas (`#f2f1ed`) with warm near-black ink (`#26251e`). The overall impression is of a well-made book, crossed with a monospaced editor, lit by afternoon light.

**Sources used for this system:**
- Written brief supplied at project start (verbatim Cursor-inspired design spec).
- No codebase, Figma, or screenshots were attached — all components here are **original interpretations** of the written spec.

### Products represented
- **ZARIS Web App** — the authoring surface: a project workspace with sidebar, document canvas, AI timeline. Treated as the core daily-driver product.
- **ZARIS Marketing Site** — the public brand surface: hero, features, pricing, documentation.

---

## 2. Content Fundamentals

### Voice and tone
- **Literary and specific**, not corporate. Sentences have rhythm. A subtitle reads like a deck line from a well-edited magazine — not a product pitch.
- **Confident, not salesy.** We make claims, we don't beg. "Built for teams that ship." Not "Empowering organizations to accelerate delivery."
- **Warm, human, first-person plural** when speaking as the company ("we believe the editor is the IDE"). Second-person **"you"** when addressing the maker ("you're five keystrokes from shipping"). Avoid "I".
- **Precise technical nouns.** Say "the composer," "the timeline," "the canvas," "a project" — named surfaces, not vague "areas."
- **Honest negatives allowed.** "Not everything needs AI. The cursor still belongs to you." This kind of principled self-awareness is on-brand.

### Casing
- **Sentence case** for all headings and buttons. Not Title Case. Not ALL CAPS (except micro system labels — see typography).
- **Lowercase** for nav items, tags, filters. `docs`, `changelog`, `pricing`.
- **Title Case** only for product names: *ZARIS Web App*, *ZARIS Composer*.
- Micro labels (11px system-ui) **may** use UPPERCASE with 0.048px letter-spacing for categorical flags like `NEW`, `BETA`, `CHANGELOG`.

### Punctuation
- Em dashes (—) over hyphens where a pause is called for. Oxford commas always.
- Numeric values in body copy use digits (`5 minutes`, `3 projects`), not words, because we speak to builders.
- Code, file paths, and keyboard shortcuts use `inline mono` with no surrounding quotes.

### Emoji
- **No emoji** in product UI, marketing copy, or docs. The brand's warmth is carried by type, color, and illustration — not by ✨ or 🚀. Emoji clutter the warm palette with cold RGB.
- Unicode symbols (→, ·, —, ↗, ⌘) are welcome and on-brand.

### Examples of on-brand copy
> **Headline:** Ship the thing you meant to make.
> **Subhead:** ZARIS is a workspace for web apps, not a form-builder with opinions.
> **Button:** Start a project · Open the composer
> **Micro:** NEW · Timeline view, in beta
> **Empty state:** No projects yet. Start one — or drop a repo here.

### Off-brand examples (avoid)
> ~~"🚀 Supercharge your workflow with AI-powered productivity!"~~ (emoji, hype verbs, generic)
> ~~"Unlock the Power of Design"~~ (Title Case, marketing cliché)
> ~~"Click here to get started!"~~ (weak, imperative-with-exclamation)

---

## 3. Visual Foundations

### Palette
The palette is **warm-shifted end-to-end**. Even the "white" is cream, the "black" is brown-black, the "red" is crimson-rose. There is no pure neutral in the system except in very rare maximum-contrast moments.

- **Canvas:** `#f2f1ed` (cream, primary page background)
- **Ink:** `#26251e` (warm near-black, primary text)
- **Surfaces:** a five-step cream scale from `#f7f7f4` → `#e1e0db`, stepping darker as emphasis grows
- **Accent:** `#f54e00` (orange) for brand moments; never for long body text
- **Hover signal:** `#cf2d56` (warm crimson) — text color shifts to this on hover, a signature interaction
- **Timeline feature colors:** peach / sage / blue / lavender — used only for AI operation states

### Type — three voices
The brand runs on three typefaces. All three are open-source, shipped with the system as variable fonts in `fonts/`, and served via `fonts/fonts.css`.

1. **Space Grotesk** — display & UI. Compressed geometric sans with aggressive negative tracking at display sizes. Weight stays at 400; hierarchy comes from size and tracking, not weight. Used for headlines, buttons, nav, and most interface labels.
2. **Fraunces** — editorial body. Serif with OpenType swash and stylistic alternates (`ss01`, `ss02`); shipped as a variable font with `SOFT`, `WONK`, `opsz`, and `wght` axes for fine control. Used for long-form reading copy, decks, and editorial counterpoint to the gothic.
3. **JetBrains Mono** — code & technical. Refined monospace tying marketing surfaces back to the editor. Used for code, file paths, keyboard shortcuts, and micro-system labels.

These are the official brand faces — not stand-ins. Reach for them in this exact split; do not introduce a fourth typeface without an explicit brand-system update.

### Backgrounds
- **Flat warm cream** is the default. No gradients behind hero content.
- **Subtle surface steps** (e.g. `#f2f1ed` → `#ebeae5`) differentiate sections — never a line, never a hard divider.
- **Editor screenshots** and **AI timeline illustrations** are the primary "imagery" — ZARIS does not use photography. If photography appears, it is warm-toned, high-grain, desaturated to cream-compatible.
- **No gradients** except very restrained vertical cream fades on oversized heroes. Never bluish-purple gradients. Never neon.
- **No repeating patterns or textures.** The paper-warmth comes from the color itself, not from a texture.

### Animation
- **Color transitions: 150ms ease.** Shadow/elevation: **200ms ease**.
- **Fades over slides** for appearing content. Subtle translate (2–4px) is acceptable.
- **No bounce, no spring.** No large-scale motion. No Lottie-style mascot animations.
- The **signature motion** is the hover text-color shift from `#26251e` → `#cf2d56` — it's quiet, instant, warm.

### Hover states
- **Text on buttons/links:** shifts to `--color-error` (`#cf2d56`).
- **Cards:** shadow intensifies (ambient → card).
- **Links:** optional warm-brown underline at 40% alpha appears on hover.
- **Never** use opacity-only hovers. Never darken/lighten a fill without an accompanying type-color shift.

### Press / active
- Subtle scale 0.985 for primary buttons. No color inversion.
- Active pill filter = one step darker surface (`#e1e0db` over `#e6e5e0`).

### Borders
- **oklab-space warm-brown borders** at three alpha levels: 10% (default), 20% (emphasized), 55% (strong).
- Fallback for older browsers: `rgba(38, 37, 30, 0.1 / 0.2 / 0.55)`.
- **No hairline grays.** A border is always warm brown, never a neutral gray.

### Shadows & elevation
- Two-layer ambient + drop shadow with **large blur values (28px, 70px)** for diffused, atmospheric lift.
- An **oklab border ring** is part of every elevated card — the warm edge is consistent regardless of surface tone.
- Cards don't "float above" the page; they feel like "the page opened a space for them."
- No inner shadows. No hard drop shadows.

### Transparency & blur
- **Used sparingly.** Sticky nav uses a `backdrop-filter: blur(12px) saturate(1.2)` on a `rgba(242, 241, 237, 0.8)` fill.
- Modals/popovers do NOT use glass/frosted effects — they use solid cream surfaces with the card shadow ring.

### Corner radii
- **Pill (9999px)** for tags, filters, badges — maximum softness.
- **8px** for primary buttons, cards, menus — the workhorse.
- **10px** for featured/larger cards.
- **4px** for compact elements; **2–3px** for inline tokens; **1.5px** for micro detail.
- **Never** use radii > 12px on rectangular elements (except pills).

### Cards
- Default: `#e6e5e0` fill, `rgba(38,37,30,0.1)` border ring, 8px radius, no fill shadow.
- Elevated: same fill, large ambient shadow, 10px radius.
- Active/hover: shadow deepens; border ring may shift to 20% for emphasized states.

### Layout
- **Max content width ~1200px**, centered.
- **Generous vertical rhythm:** section padding 80–120px on desktop, 48px on mobile.
- **Warm negative space** — whitespace *is* the canvas. Don't fill corners with logos or decorative flourishes.
- **Compressed text, open layout.** Headlines are tight; margins are breathing.

### Imagery color vibe
- Warm. Desaturated. Slight grain tolerated. Never cool, clinical, or synthetic-looking.
- Editor screenshots use **dark warm-brown backgrounds** (`#26251e`-tinted) with cream text — the inverse of the canvas.

---

## 4. Iconography

ZARIS uses **Lucide** ([lucide.dev](https://lucide.dev)) as its icon system, loaded from CDN or npm. It's chosen because:
- Stroke-based, consistent 1.5–2px stroke weight (matches the precise, engineered feel of the type).
- Sized at 14–16px to match UI labels.
- Warm neutral rendering — takes on ink color cleanly.

### Rules
- Icon color: **always `currentColor`**, inheriting from the surrounding text (usually `--fg-1` or `--fg-3`). Never colored in brand orange except when replacing or accompanying a link.
- Stroke width: **1.5px** default, **2px** for high-emphasis actions.
- Icon button pattern: 14px icon + 14px Space Grotesk label with 8px gap.

### Custom marks
- `assets/zaris-logo.svg` — wordmark in display type
- `assets/zaris-mark.svg` — condensed Z monogram for favicon/app icon
- `assets/illustration-timeline.svg` — AI timeline metaphor illustration

### Usage rules
- **No emoji** in product UI.
- **Unicode arrows** (→, ↗, ↘) are permitted inline in copy for flow and directionality.
- **No drawn or hand-rolled decorative SVGs.** All iconography comes from Lucide or the ZARIS marks above.

---

## 5. Spacing Philosophy

- **Base unit: 8px.** Most spacing is multiples of 8: 16, 24, 32, 48, 64, 96.
- **Fine sub-8 scale:** 1.5, 2, 2.5, 3, 4, 5, 6px — used for icon/text micro-alignment. When your 14px icon sits next to a 14px label, a 6px gap feels right; not 8px.
- **Section rhythm:** 80–120px vertical on desktop, 48px mobile.
- **Never mix scales arbitrarily.** If you're already at 16px, don't jump to 20 — go to 24.

---

## 6. Depth & Elevation Quick Ref

| Level | Treatment | Where |
|---|---|---|
| 0 | no shadow | body text, page bg |
| 1 | `0 0 0 1px oklab(0.263/0.1)` | card/container border ring |
| 1b | `0 0 0 1px oklab(0.263/0.2)` | active/emphasized borders |
| 2 | ambient glow (16px + 8px) | floating elements, chips |
| 3 | card shadow (28px + 70px + ring) | modals, popovers, featured cards |
| focus | `0 4px 12px rgba(0,0,0,0.1)` | interactive focus |

---

## 7. Caveats & Things to Verify

- **No real product source:** no codebase, no Figma, no screenshots — the UI kits are interpretations, not recreations. Please attach any real product screenshots or a Figma link if you want tighter fidelity.
- **Timeline colors** are defined but the AI Timeline component is only lightly sketched; if the real product has additional operation types, add them to the palette.

---

Made with care. Warm, precise, opinionated.