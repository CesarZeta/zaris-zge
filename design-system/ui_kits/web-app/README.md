# ZARIS Web App — UI Kit

An interpretation of the ZARIS authoring surface: a project workspace with sidebar, document canvas, composer, and the AI timeline.

## Files
- `index.html` — interactive click-through
- `Sidebar.jsx` — left project/navigation rail
- `TopBar.jsx` — workspace top bar w/ breadcrumb, search, user
- `Composer.jsx` — AI input composer with pill actions
- `Timeline.jsx` — AI operation timeline (Thinking / Grep / Read / Edit)
- `DocumentCanvas.jsx` — the main content canvas
- `ProjectCard.jsx` — project tile for grid/list views
- `CommandMenu.jsx` — cmd-k style command palette (modal overlay)
- `Primitives.jsx` — Button, Pill, Badge, Input, Card, IconBtn

## Notes
Pixel-perfect to the spec in `../../colors_and_type.css`. Since no real codebase or Figma was attached, component internals are cosmetic only — they look right, they don't do business logic.
