# FlowTodo native UI design system

## Product context

FlowTodo is a calm, local-first desktop task and focus app for Windows. The account area should help a user understand momentum at a glance and then choose a day to plan or review. Prefer several focused surfaces over one dense dashboard.

## Visual direction

- Native RinUI / Microsoft WinUI: quiet F3F3F3 light background, translucent white cards, 1px low-contrast borders, 7px window radius, 5px control radius.
- Use the runtime RinUI accent through `Theme.currentTheme.colors.primaryColor`; supporting colors are Fluent blue `#0f6cbd`, green `#0f7b0f`, purple `#8764b8`, orange `#d83b01` only for meaning.
- Use RinUI `Typography` roles. Keep page padding around 34-36px and gaps around 8-14px.
- Avoid gradients, decorative hero art, oversized charts, dense tables, and custom fonts.

## Account / calendar surface

Use a two-level structure: a concise account header and metrics, then an activity card with a GitHub/Codex-like square calendar. The calendar is a 7-column weekday grid with compact square cells and a small legend. It should show a rolling 12-week focus history, with stronger primary-accent fill for more focused minutes, a distinct outlined today cell, and a selected day that updates the adjacent detail panel. The adjacent detail panel lists the selected date's planned tasks and focus minutes, leaving whitespace rather than packing all days into one table.

## Interaction rules

- Account overview stays readable at 900px minimum window width.
- Clicking a calendar square selects that date and updates a small detail card.
- A `查看日程` action opens a dedicated multi-day schedule page with a week strip and agenda list.
- Keep controls familiar: RinUI `Button`, `ToolButton`, `Segmented`, `Frame`, and `Icon`.

Use ONLY the fonts, colors, spacing, and component styles defined in this design system. Do not introduce any fonts, colors, or visual styles not in the design system.
