# CloudCostLens — UI Design System

The interface must read like a mature enterprise FinOps tool: restrained, structured,
information-dense, and easy to scan. **Dark-mode first.**

## 1. Design tokens

Implemented as CSS variables in `apps/web/app/globals.css` and mapped into Tailwind in
`apps/web/tailwind.config.ts`. Components reference tokens (not raw hex).

| Token | Value | Use |
|---|---|---|
| `--bg-app` | `#0B1020` | Application background |
| `--bg-sidebar` | `#0E1528` | Sidebar |
| `--bg-surface` | `#141D32` | Primary surface (cards, panels) |
| `--bg-surface-2` | `#182238` | Secondary surface (table header, hover) |
| `--border` | `#283449` | Borders, dividers |
| `--text-primary` | `#F3F6FC` | Primary text |
| `--text-secondary` | `#A5B1C5` | Secondary/labels |
| `--accent` | `#4F8CFF` | Primary actions / neutral info |
| `--accent-2` | `#37C8E8` | Secondary accent |
| `--success` | `#32B67A` | Verified success / savings |
| `--warning` | `#E8AA43` | Review required |
| `--critical` | `#E66B72` | Critical risk / failure |

Contrast is validated for text-on-surface combinations. Tokens are the **only** source of
color for meaning.

## 2. Color semantics

Color is used for meaning and **never alone**:

- Green = verified success or confirmed savings.
- Amber = review required / medium risk.
- Red = critical risk or failure.
- Blue = primary action or neutral information.
- Gray = inactive / secondary.

Every status also carries a **text label** and, where useful, a shape/icon so the meaning
survives color-blindness and grayscale printing.

## 3. Typography & spacing

- One clean sans-serif family across the app (system UI stack or Inter).
- Restrained scale: page title, section title, body, caption. No oversized display type
  inside the application.
- 8-point spacing grid for margins, padding, and component rhythm.
- Tabular numerals for all financial/metric figures.

## 4. Layout

- Fixed sidebar (wordmark, navigation, connected-account indicator, user/org context).
- Compact top control bar per page: title + one-line description on the left; account,
  region, and date-range selectors, "last refreshed", and refresh/scan controls on the right.
- Scrollable main region. Filters persist within a page.
- Compact KPI rows — **not** a grid of giant cards.

## 5. Components (shadcn/ui + custom)

`AppShell`, `Sidebar`, `PageHeader`, `ControlBar`, `KpiStat`, `DataTable`
(sorting/pagination/CSV), `StatusBadge`, `RiskBadge`, `EvidencePanel`, `MetricCoverage`,
`ResourceDetailTabs`, `ChartCard` (ECharts wrapper), `EmptyState`, `DemoDataBanner`,
`ConfirmDialog`.

Consistent control heights, table density, and section spacing across every page.

## 6. Charts (Apache ECharts)

Shared dark theme: transparent background, `--text-secondary` axis labels, `--border`
gridlines, series palette drawn from accent/semantic tokens. No decorative gradients,
no 3-D, no animation beyond subtle transitions.

Charts are **analytical**, never ornamental: spend trend, spend by service, opportunities
by category, top cost drivers, stacked cost breakdown, cost-change comparison.

## 7. States

Every data view defines: loading (skeleton), empty, error, partial (incomplete scan),
and — when showing demonstration fixtures — a persistent, unmissable **"Sample data"**
banner plus per-value labels. Missing telemetry renders as "No data", never as `0`.

## 8. Anti-patterns (explicitly forbidden)

Gradients, glowing/neon borders, glassmorphism, decorative blobs, giant rounded cards for
every metric, excessive shadows, oversized headings, large empty areas, random icon
placement, emoji as UI icons, fake/analytical-less charts, repeated identical card layouts,
in-app marketing hero sections, gratuitous animation, 3-D graphics, invented real-time
indicators, percentages without a defined calculation, and non-functional AI buttons.

## 9. Accessibility

- Semantic HTML via Radix primitives; keyboard operability; visible focus.
- Minimum contrast AA for text; status conveyed by text + color.
- Tables expose header semantics; charts include accessible summaries/titles.
- Dates shown in the user's locale; stored/transmitted values are UTC.

## 10. Content rules

- Every displayed metric has a documented calculation (linked in the page or tooltip).
- Measured facts, derived estimates, and illustrative data are visually distinguished and
  labeled ("Estimated", "Sample data", "Source: Cost Explorer, updated …").
- Actions state exactly what will happen and whether they are reversible.
