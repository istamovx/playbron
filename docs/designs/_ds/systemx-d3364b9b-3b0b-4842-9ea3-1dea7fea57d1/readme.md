# SystemX Design System

SystemX is a dark, instrument-grade design system for a **security-operations console**: an
analyst workspace where threat telemetry is triaged as investigations, entities
(users, files, apps, endpoints) are inspected, and remediations are dispatched.
The visual language is HUD/tactical — near-black surfaces, 1px hairlines,
chamfered corners, one saturated violet for anything interactive, and a red/tan
risk ramp reserved strictly for data.

The product name is not stated in the sources. **SystemX** is the name given to
this design system by its owner; it is not a claim about the company behind the
original screenshots.

## Sources supplied

| Source | What it gave |
| --- | --- |
| `uploads/original-d429f4eb48c289cacb1af3866f25692a.webp` | Entity profile board + investigation queue + unauthorized-access summary + investigation detail |
| `uploads/original-c653da86203122754060f59d2ed22c8c.webp` | Overview dashboard + investigation detail, overlapping |
| `uploads/original-7cf4d9901665050dee48338693907bd6.webp` | Overview dashboard, full frame |
| `uploads/pasted-1786345283710-0.png` | Investigation detail, full frame at 1:1 — the highest-fidelity screen reference |
| `uploads/pasted-1786345301580-0.png` | **Brand colour sheet** (exact hex ramps) + full icon sheet (~130 filled glyphs) |
| `uploads/Xarita.ts` / `uploads/Xarita.cjs.js` | Uzbekistan SVG path data — 14 regions + the Aral Sea, plus per-district paths (districts not imported) |

No codebase, Figma file, font binaries, icon SVGs, logo, or map imagery were
supplied. Everything below was read off those images; exact hexes come from the
colour sheet, exact control geometry was measured from the 1:1 screenshot.

## Index

- `styles.css` — the one file consumers link. `@import` list only.
- `tokens/` — `fonts.css`, `colors.css`, `typography.css`, `spacing.css`, `effects.css`, `theme-light.css`, `breakpoints.css`, `base.css`
- `guidelines/` — foundation specimen cards (Colors, Type, Spacing, Brand, Layout)
- `components/` — see the component list below
- `ui_kits/soc-console/` — `index.html`, `AppShell.jsx`, `OverviewScreen.jsx`, `InvestigationScreen.jsx`, `EntityScreen.jsx`, `GeoScreen.jsx`, `LoginScreen.jsx`, `login.html`, `README.md`
- `assets/uzbekistan-regions.js` — region outlines extracted from the supplied `Xarita.ts`
- `assets/` — see ASSETS; **no logo ships with this system**
- `SKILL.md` — Agent-Skills wrapper

### Components

`components/primitives/` — **Button**, **IconButton**, **Chip**, **Tag**, **Avatar**, **Icon**, **PlateChip**, **StatusLine**
`components/surfaces/` — **Panel**, **ListCard**, **ActionItemCard**, **HoverCard**, **CameraFeed**, **PageHeader** (+ **ServerClock**)
`components/navigation/` — **Tabs**, **SegmentedControl**, **SidebarRail**, **SidebarNav**, **UserMenu**

**Navigation directions.** `SidebarNav` ships three interchangeable shells —
`expand` (pinned open at 208px with a collapse toggle; the console default),
`docked` (always open, no toggle) and `command` (horizontal 52px strip, full-width
workspace). `SidebarRail` is the original icon-only rail from the source
screenshots and is kept unchanged. Pick one per product; never mix two in one app.
The SOC console demo exposes all four via a switcher in the bottom-right corner
and a `?nav=` URL parameter.
`components/forms/` — **Select**, **TextField**
`components/data/` — **Metric** (+ **MetricCell**), **FieldRow** (+ **FieldBlock**), **RiskLegend**, **InteractionTimeline**, **RadialScatter**, **ActivityBars**, **EntityTable**, **EntityGraph** (+ **EntityCountList**), **ConnectorItem**, **SlotGrid** (+ **SlotCell**), **Legend**, **GateMarker** (+ **FlowLane**)
`components/charts/` — **RegionMap**, **DonutGauge**, **RankedBars**, **AreaTrend**, **HeatMatrix**, **ProgressMeter**, **StatTile**, **CapacityBar**
`components/layout/` — **Responsive** (namespace handle) exporting **useBreakpoint**, **Show**, **Grid**, **ConsoleLayout**, **Stack**, **ScrollX**

Every component has a sibling `.d.ts` (props contract) and `.prompt.md` (what &
when + usage). Each directory has one `@dsCard` HTML showing its states.

**Intentional additions** (not literally a component in the source, but needed):
- `Icon` — wrapper for the glyph set, so no screen inlines SVG.
- `components/charts/*` — the source screenshots contain four chart types; the seven
  widgets in this group extend that vocabulary (gauge, ranked bars, trend line,
  heat matrix, segmented meter, KPI tile, region map) **using only the existing
  encodings** — the same risk ramp, hairline tracks, chamfered cards and rationed
  glow. `RegionMap` exists because the user supplied Uzbekistan path data.
- `Panel` — the source has no single named container, but every region shares one
  treatment; formalising it prevents drift.
- `MetricCell`, `FieldBlock`, `EntityCountList` — sub-variants of their file's
  main component, both visible in the screenshots.
- `TextField` — the source screens contain no input at all, but authentication
  needs one. Geometry is copied from `FieldRow` so it joins the same ladder.
- **Access-control family** (`PlateChip`, `StatusLine`, `CameraFeed`, `SlotGrid`,
  `Legend`, `GateMarker`, `CapacityBar`, `PageHeader`, `UserMenu`) — harvested back
  out of a real parking-control product built on this system, so they are proven
  in use rather than speculative. They generalise the console's grammar to
  *physical* monitoring: things the system saw, places it manages, gates it
  controls. See DOMAIN PLAYBOOKS.
- `components/layout/*` — the source is a single fixed-width desktop console. Real
  projects need phone and tablet, so the system adds breakpoint tokens and six
  layout primitives rather than leaving each project to invent its own.

**Not built, because the source never shows them:** textarea, checkbox, radio,
switch, slider, modal/dialog, toast, breadcrumb, pagination, accordion. Do not
invent them; ask first.

---

## CONTENT FUNDAMENTALS

**Voice: instrument, not assistant.** The UI reports state; it never chats,
apologises, or celebrates. There is no first person and almost no second person —
no "You have 20 action items", just `Action Items (20)`.

**Casing**
- Panel and section titles: **Title Case or sentence case, mixed by scope.**
  Nouns naming a region are Title Case (`Investigations`, `Exposed Entities`,
  `Connectors`, `Guide`, `Action Items (20)`, `Recommended Remediations`,
  `Investigations Over Time`). Descriptive chart captions are sentence case
  (`Interactions over time`, `Entities and Interactions`).
- Page titles: **ALL CAPS** in the display face (`MALWARE INFECTION`).
- Field labels above a box: **10px ALL CAPS**, wide tracking (`DESCRIPTION`,
  `ROLES`, `DEPARTMENTS`, `SOURCE ENTITY`, `TARGET ENTITY`, `RECENT`, `TOTAL`,
  `LOW`, `MEDIUM`, `HIGH`, `ACTIVE`).
- Inline field labels: **Title Case with a colon** (`Score:`, `End Time:`,
  `Start Time:`, `Assignee:`, `Contact No.:`, `Location Info:`,
  `Last Active Location:`, `First Detected At`, `Related Entities`).
- Machine event names: **SCREAMING_SNAKE** (`DATA_BREACHES`,
  `SUSPICIOUS_SQL_QUERY_DETECTED`, `UNAUTHORIZED_ACCESS_ATTEMPT`,
  `MALWARE_DETECTED`).

**Counts live inside the label, in parentheses** — `Investigations (2)`,
`Comments (7)`, `Devices (5)`, `Permissions (12)`, `Action Items (20)`. Never a
separate badge bubble.

**Recommendations are imperative verb phrases, unpunctuated:**
"Remove malware from a compromised system", "Isolate compromised endpoint from
network", "Reset compromised user account password", "Enforce multi-factor
authentication and conditional access policies", "Apply latest patches to web
applications and databases". No "Consider…", no "You should…", no trailing period.

**Descriptions are one flat definitional sentence.** "An unauthorized access
investigation aims to identify, analyze, and resolve security incidents where
users have gained unauthorized access to systems or data." US spelling (analyze).

**Deltas are terse and additive:** `+15 in last 24 hours`, `+ 4.9k in the last 24
hours`, `4 new in the last 24 hours`. Green, small, beside the number.

**Buttons are one word where possible** — `View`, `Actions`, `Details`,
`Investigate`, `Graph`, `Table`, `All`. Time ranges are `1 Day` / `1 Week` /
`1 Month` / `Last 3 days`.

**Data formats.** Timestamps `YYYY-MM-DD HH:MM:SS` in mono; list-row dates
`MM-DD-YYYY hh:mm:ss AM`. Case ids `CS-123`. Scores are bare integers preceded by
a dot-matrix glyph. Phone `+1 (555) 123-4567`. Locations `City, ST`.

**No emoji, ever.** No exclamation marks. No sentence-ending periods on labels,
titles, or button text. Ellipses only in genuine truncation.

**Empty states say what is missing, plainly** — this system prefers a dashed
outline with a flat statement over an illustration or a cheerful nudge.

---

## VISUAL FOUNDATIONS

**Colour.** One brand hue: violet, `--primary-100 #5700FF` at its brightest,
darkening to `#160040`. It carries *all* interactivity — frames, active tabs,
selected rows, focus rings, the rail's active diamond, the one primary button.
Everything else on screen is achromatic near-black plus white text. The secondary
ramp (`#F5BD99 #EC7E84 #E1327C #E481CF #32E197`) and status colours
(`#980043 #FF505D #B661DE #EDB07E`) appear **only in data and status**: risk
dots, severity counts, `ACTIVE` connector labels, the amber `Expected` tag. Never
use them for decoration or as surface fills. Roughly 92% of pixels are neutral.

**Surfaces.** The app floats on pure black (`--void-0`) with a 96px grid at 3.5%
white. The chassis is `--void-2` inside a 1px `#5700FF` border with a large soft
outer glow and an 18px radius — the *only* soft corner in the system. Panels are
`--void-4` at 1px `rgba(255,255,255,.08)`. Field boxes are `rgba(255,255,255,.03)`.
Panels never carry drop shadows; only floating popovers do
(`--shadow-pop`, plus 6px backdrop blur at 96% black).

**Corner radii.** 2px on virtually everything (`--r-1`); 3–5px only where a
control needs to read softer; 18px on the outer chassis; full-round reserved for
avatars, risk dots and graph nodes. There are **no rounded cards** in this
system — the softness budget is spent entirely on the chassis.

**The HUD tell: chamfers and brackets.** A 14px 45° cut on the top-right corner
(`--clip-tr`) appears on tabs, list cards, action cards, metric cells, popovers,
the header Actions control and most panels. Four 10–14px L-shaped tick marks
(`--line-3`) mark the bounds of the workspace and of focused detail panels.
Bracket ticks also flank the time-range switcher (`[ 1 Day ][ 1 Week ][ 1 Month ]`).
Horizontal rules are frequently *broken* — a short bright segment, a long dim
segment, a short bright segment — never one continuous line under a page title.

**Type.** Two faces. A squarish techno sans for everything human-readable
(page titles 30px/700/uppercase, panel titles 16px/400, body 13px/1.45, controls
12px/500, labels 10px/500 with .10em tracking, metrics 38px/500) and a monospace
for everything machine-generated (timestamps, IPs, ids, event names, axis ticks,
edge labels). The pairing rule is absolute: a label is never mono, a value is
never not. Panel titles are **regular weight** — bold is reserved for page titles.

**Spacing & density.** 2px base scale; the working gaps are 6/8/12/14/20px.
Control heights are 22 / 26 / 30 / 34px; field rows 28px; panel padding 14px;
card padding 12px; nav rail 56px; detail sidebar ~300–352px; action aside ~268px.
Field-row stacks use a 2px gap so they read as one contiguous ladder.

**Backgrounds & imagery.** No photography, no illustration, no texture beyond two
generated fields: the 96px square grid and an 8px dot matrix (used as a small
"data" glyph beside scores and popover titles). No decorative gradients anywhere —
the only gradients in the system are the radar sweep wedge (white 9% → 0) and
faint spoke fades. If imagery is ever added it should stay cool, desaturated and
dark; nothing warm or bright competes with the risk ramp.

**Charts are the imagery.** The polar scatter (angle = day of month, radius =
hour, dot size + colour = risk), the 24-hour interaction lane, the grey
throughput histogram, and the node/edge entity graph. Rings are dotted at 6%
white, spokes fade upward, edge ticks are two-digit mono day numbers. Grey is the
default; colour means severity.

**Transparency & blur.** Sparingly and only for floating layers: popovers at 96%
black + `blur(6px)`. Panels are opaque. Tints are used instead of opacity for
state: selected = `rgba(87,0,255,.18)`, hover = `rgba(255,255,255,.055)`,
risk row = `rgba(255,80,93,.06)`.

**Shadows.** Effectively no elevation system. `--shadow-panel` exists but is used
almost nowhere; `--shadow-pop` for popovers; graph nodes get a 4px pure-black halo
so edges pass behind them cleanly. Depth comes from hairlines, not shadow.

**Glow is the accent system, and it is rationed.** `--glow-violet-lg` on the
chassis only. `--glow-violet-sm` on the active tab, the open dropdown, a hovered
primary button, the rail diamond. `--glow-risk` on at-risk dots. Nothing else
glows — no glowing text, no glowing panels.

**States.**
- *hover*: background lightens ~4–6% white, border steps `--line-2 → --line-3`;
  interactive violet surfaces step `--primary-500 → --primary-400`; text
  `--fg-3 → --fg-1`. 140ms.
- *press*: `translateY(1px)` and background back down. **Never scale, never bounce.**
- *selected*: violet fill (tabs, segments) or 18% violet tint + `#5700FF`
  hairline + a 2px violet left rail (list rows) + semibold title.
- *expanded* (table row): 10% violet tint, value text underlined, chevron flips.
- *disabled*: `--fg-4` on 2% white, hairline stays `--line-1`, `not-allowed`.
- *focus*: `--border-focus` (`#4E00E5`); the system leans on border colour rather
  than an offset ring.

**Motion.** 90/140/220/400ms with `cubic-bezier(.22,.61,.36,1)`. Colour and
border transitions only; layout does not animate. No bounce, no spring, no
easing-in of whole panels. The sole ambient motion is the radar sweep, and even
that is static in the source.

**Layout rules.** Fixed 56px rail, fixed-width detail sidebar and action aside,
one fluid middle column that owns the hero chart or table. Everything above the
fold; internal columns scroll independently rather than the page. Charts are
generously surrounded by dead space — emptiness reads as calm instrument, not as
missing content.

---

## ICONOGRAPHY

The brand's own icon set is visible on the supplied colour/icon sheet: roughly
**130 solid (filled) monochrome white glyphs on a 24px grid**, security-domain
specific — shields (plain, check, bad, person), locks and keys (locked, unlocked,
locked-message, key), wifi states (on, off, home-wifi, warning-home), cloud and
cloud-off, VPN, firewall/brick wall, bug/malware, virus, spider/crawler, hacker
mask, fingerprint, endpoints (laptop, desktop, phone, tablet, watch, headset),
documents (file, file-text, file-question), identity (person, badge, ID card,
face variants), scanning (search-in-window, magnifier, filter, radar/target,
crosshair-node), edit/pencil, tag, eye and eye-off, toggles, chevrons in all four
directions, github/grid/window/calendar utility glyphs, and dot-cluster "entity
node" marks. Style is uniform: **filled, no strokes, no two-tone, no colour** —
colour is applied only by context (white by default, `--risk-high` for danger,
`--green-400` for active).

Emoji: **never used.** Unicode characters as icons: **not used**, with two
exceptions that are really typography — the dot-matrix glyph beside a score
(rendered as a CSS dot pattern, not a character) and the `[` `]` HUD tick marks
flanking the range switcher (rendered as 1px divs).

**⚠ Substitution.** Those glyphs were only provided as a flat raster sheet — no
SVG, font, or sprite. This system therefore ships **Material Symbols Rounded at
FILL=1** via the Google Fonts CDN (imported in `tokens/fonts.css`), which is the
closest available match for weight, grid and solid fill. All icon references use
Material glyph names (`verified_user`, `expand_more`, `hub`, `track_changes`,
`screen_search_desktop`, `filter_alt`). The mapping is centralised in
`components/primitives/Icon.jsx` — **replace the font stack there** and the whole
system updates. Please send the real icon set as SVG or a webfont.

Always render icons through `<Icon name="…" />`. Never inline SVG, never
hand-draw a glyph, never use an outline icon set.

## ASSETS

`assets/` contains **no logo and no imagery**, because none was supplied:

- **No logo/brand mark.** The screenshots show a small violet mark in the rail,
  but reconstructing it from a screenshot would be inventing a company's mark.
  Wherever a mark belongs, this system renders the wordmark (or its initial) in
  the display face, violet, with `--glow-violet` — see `Brandmark` in
  `ui_kits/soc-console/AppShell.jsx`.
- **No map tiles.** The entity panel's dark street *city* map is a labelled dashed
  placeholder (`MapPlaceholder` in `EntityScreen.jsx`). The **country** map is real:
  `assets/uzbekistan-regions.js` holds the region outlines extracted verbatim from
  the supplied `Xarita.ts`, rendered by `RegionMap`. Per-district paths exist in
  that source file but were not imported — ask before adding a drill-down.
- **No vendor logos.** Microsoft Defender / Azure AD connectors fall back to icon
  glyphs; `ConnectorItem` accepts a `logo` path if you add them.
- **No photography or illustration** exists in this product's language, so none is
  needed.

## LIGHT MODE

The console is authored dark. Light mode is **not an inversion** — an inverted HUD
looks like a toy. It is a re-derivation of the same three rules onto paper.

**Turn it on:** `document.documentElement.setAttribute("data-theme","light")`.
Any subtree works too (`<div data-theme="light">`), which is how the specimen card
shows both at once. Components need no changes: they read semantic tokens, and
`tokens/theme-light.css` redefines those tokens inside `[data-theme="light"]`.

**What changes, and why.**

| Dark | Light | Reason |
| --- | --- | --- |
| Near-black `#07070A` app, panels *lighter* | Cool paper `#EBEBF0` app, panels *white* | Elevation must still read; on paper that means panels go lighter than their surround, the same direction as dark |
| Pure white text | Graphite `#14141A` | Pure black on paper is harsh and loses the cool cast that makes this system feel like an instrument |
| 8% white hairlines | 11% graphite hairlines | An 8% line is invisible on paper; structure is carried by lines in both themes, so they must stay legible |
| **Glow** marks interaction | **Weight** marks interaction | Light cannot glow. `--glow-violet-sm` becomes a 1px violet ring; `--glow-violet-lg` becomes a soft drop shadow. The cue survives, the metaphor changes |
| `#5700FF` for fills *and* text | `#5700FF` fills only; `#4500CC` for text/icons | The bright violet fails contrast as small text on white |
| Tan `#EDB07E`, salmon `#EC7E84` | `#B87333`, `#C4515C` | The light risk tiers wash out on paper and must darken to stay a ramp |
| Red `#FF505D` + halo | `#D91E32`, no halo | Red keeps its identity; severity is carried by size and saturation instead of light |
| Green `#32E197` | `#0E8F5C` | Mint green is illegible on white |

**What does not change.** Geometry, spacing, type, the 14px chamfer, corner
brackets, the dot/grid fields, motion timings, and the rule that colour means
data. A screen should be recognisable as the same product in either theme.

**Rules when building for light.**
1. Never hardcode a colour in a component. Every literal was moved to a token
   (`--surface-hover`, `--chart-track`, `--map-2`, `--surface-pop`, …) precisely so
   light mode is a stylesheet, not a fork. If you need a new colour, add a token
   in both themes.
2. Panels get `--shadow-panel` on light and nothing on dark. That is the one
   place the themes legitimately diverge structurally.
3. Do not soften the palette further. The temptation on light is pastel; resist
   it. This is still an operations console.
4. Charts read from `--chart-*` and `--map-*` tokens. Retune those, never the
   chart component.

**Not themed:** the login screen's ambient cyber field is dark-only by intent — a
scanning radar on white reads as decoration. It keeps `data-theme="dark"`.

## RESPONSIVE SYSTEM

The source console is a fixed-width desk instrument. This system makes it work on
phone, tablet and desk **without a second design language** — the density relaxes,
the columns collapse, nothing is redrawn.

**Breakpoints.** `xs` 0 · `sm` 600 · `md` 905 · `lg` 1240 · `xl` 1600.
Declared as `--bp-*` tokens and mirrored literally in `tokens/breakpoints.css`
media queries and in `useBreakpoint()`. Keep the three in sync if you change them.

**The core idea: tokens adapt, components don't.** `--gutter`, `--gap-panel`,
`--panel-pad`, `--detail-w`, `--aside-w` and the four `--control-h*` tokens are
redefined per breakpoint. Because every component sizes itself from those tokens,
one stylesheet block adapts the entire library. Write a component once; it is
responsive by construction.

**Touch is a pointer question, not a width question.** A `@media (pointer:coarse)`
block raises `--control-h` 26 → 40px, `--control-h-lg` 34 → 48px and `--field-h`
28 → 44px. Every control clears the 44px target on a touch device — including a
touchscreen wall display at 1920px, which a width-based rule would miss.

**Layout ladder** (reach for these in order):
1. `.ds-grid` / `<Grid min={260}>` — auto-fit collections. No media query, ever.
2. `.ds-console` / `<ConsoleLayout>` — the 3-column shell; 3 → 2 columns at `lg`, → 1 at `md`.
3. `<ScrollX>` — telemetry tables scroll sideways rather than crush. The one place horizontal scrolling is correct.
4. `useBreakpoint()` — only for *structural* changes: a different component, a different chart size (`bp.pick({ base: 250, lg: 520 })`).
5. A hand-written media query — last resort; if you need one, consider whether a token belongs there instead.

**Per-surface behaviour.**
- *Navigation* — `SidebarNav` swaps itself for a 56px bottom bar (5 targets + overflow sheet) at `sm`, or a hamburger drawer with `mobile="drawer"`. Between `md` and `lg` the expand rail starts collapsed.
- *Charts* — `RegionMap`, `AreaTrend`, `HeatMatrix`, `RankedBars` and `ProgressMeter` are fluid; `RadialScatter` and `DonutGauge` take an explicit `size`, so drive them with `bp.pick`.
- *Tables* — `EntityTable` keeps its columns and scrolls. Do not collapse telemetry rows into cards; the source/target pairing is the meaning.
- *Type* — `--fs-title-fluid` and `--fs-metric-fluid` clamp hero text so it shrinks without breakpoints. Body text never shrinks below 12px on any device.
- *Motion* — `prefers-reduced-motion` is honoured globally in `tokens/breakpoints.css`.

**Minimums.** Never render body copy below 12px, never a touch target below 44px,
never let a panel go below 260px wide before it stacks.

## DOMAIN PLAYBOOKS

This system was read off a security-operations console, but its grammar —
near-black chassis, hairline panels, one violet for interaction, a risk ramp for
data, mono for machine values — fits any **monitoring / control-room** product.
Below is how to map each domain onto the existing components. In every case:
reuse the vocabulary, do not invent a second visual language.

Shared skeleton for all four:

```
SidebarRail (icon-only)  →  page title + Select("Actions")  →
  left Panel (entity/detail, brackets)  |  centre Panel (live view / hero chart)  |  right Panel (action items)
  footer: ActivityBars (throughput)
```

### 1. CCTV surveillance monitoring

| Need | Use |
| --- | --- |
| Camera grid / wall | `CameraFeed` in a `Grid min={260}`; `offline` for dead channels |
| Selected camera detail | `Panel brackets` + `FieldRow` stack (Stream, Codec, Bitrate, Last motion) |
| Event timeline | `InteractionTimeline` — motion/intrusion events on the 24-hour lane |
| Motion heat by hour | `HeatMatrix` |
| Site map / camera coverage | `RegionMap` for multi-city fleets; a floor plan is **not supplied** — placeholder it |
| Alerts queue | `ListCard` (id = camera id, title = event), `ActionItemCard` for "Review footage" |
| Recognition verdict | `PlateChip` in `CameraFeed`'s `detection`, `StatusLine` underneath |
| Counters | `Metric` (cameras online / total), `MetricCell` (offline / degraded / recording) |
| Health | `ProgressMeter` (storage days retained, threshold = policy minimum) |

Copy: `MOTION_DETECTED`, `LINE_CROSSED`, `CAMERA_OFFLINE`, `TAMPER_DETECTED`.
Ids like `CAM-014`. Never label a feed with a friendly sentence — `Gate 2 · CAM-014`.

### 2. Parking control

| Need | Use |
| --- | --- |
| Occupancy | `DonutGauge` headline; `CapacityBar` per floor and zone (one block per bay) |
| Live gate events | `EntityTable` — event `ENTRY_GRANTED` / `EXIT_DENIED`, source = plate, target = gate |
| ANPR gate | `CameraFeed` + `PlateChip` + `StatusLine` + a `Button` row |
| Session detail | `Panel brackets` + `FieldRow` (Plate, Entry time, Duration, Tariff, Amount) |
| Turnover trend | `AreaTrend`; peak hours → `HeatMatrix` |
| Busiest gates / zones | `RankedBars` |
| Barrier / device status | `ConnectorItem` |
| Bay layout | `SlotGrid` + `Legend`, with `GateMarker`/`FlowLane` between zones |
| Blacklist / permit tags | `Chip` (permit classes), `Tag tone="danger"` (blacklisted) |
| City-wide lots | `RegionMap` |

Copy: mono plates (`01A123BC`), durations as `02:14:38`, money as a bare mono
number with a caps currency label. Actions: `Open barrier`, `Void session`.

### 3. GPS fleet tracking

| Need | Use |
| --- | --- |
| Fleet on the country map | `RegionMap` with `markers` per vehicle cluster and `data` risk tint per region |
| Vehicle list | `ListCard` (id = plate, title = route / driver), plates as `PlateChip plain` |
| Vehicle detail | `Panel brackets` + `FieldRow` (Speed, Heading, Odometer, Ignition, Last ping) |
| Trip timeline | `InteractionTimeline` (stops, idles, speeding events) |
| Speed / fuel trend | `AreaTrend` |
| Route graph (stops as nodes) | `EntityGraph` |
| Violations ranked | `RankedBars` (`tone="risk"`) |
| Live counts | `StatTile` (moving / idle / offline, with sparkline) |

Copy: `OVERSPEED`, `GEOFENCE_EXIT`, `IGNITION_OFF`, `SIGNAL_LOST`.
Coordinates and speeds are mono; a street-level map is **not supplied** — use
`RegionMap` for the country view and placeholder the street view.

### 4. Biocontrol — biometric access & HR

| Need | Use |
| --- | --- |
| Employee profile | `EntityScreen` pattern verbatim: `Avatar square`, email/id, `Tabs` (Details / Devices / Permissions), `Chip` for roles + departments, `FieldRow` for contacts |
| Attendance by day/hour | `HeatMatrix` (present / late / absent intensity) |
| Punch log | `EntityTable` — `CHECK_IN`, `CHECK_OUT`, `ACCESS_DENIED`; source = employee, target = door |
| Badge scan / turnstile | `CameraFeed` + `PlateChip` (badge id) + `StatusLine` |
| Desk / locker allocation | `SlotGrid` with `state="assigned"` |
| Late-arrival trend | `AreaTrend`; departments ranked → `RankedBars` |
| Headcount / attendance rate | `Metric`, `StatTile`, `DonutGauge` (attendance %, `tone="ok"`) |
| Door / terminal status | `ConnectorItem` |
| Discipline actions | `ActionItemCard` ("Request explanation", "Escalate to HR") |
| Offices by region | `RegionMap` |

**Tone caution.** This is the one domain where the console's cold voice needs
softening: it describes people, not threats. Keep the casing and mono/UI-face
rules, but drop the risk-red ramp for routine states — reserve red for genuine
security events (forced door, denied access), and use `--yellow-100` for "late"
and `--secondary-500` for "present". Never render an employee as "At Risk".

### What each domain would need added

None of these exist yet — **ask before building**, and add them as new component
files in the existing groups so they inherit the vocabulary:

- **Floor plan / street map** (CCTV, Parking, GPS) — needs real geometry from you; `RegionMap` only covers Uzbekistan at region level.
- **Shift / roster strip** (Biocontrol) — a horizontal day-band; `HeatMatrix` covers most of this already.
- **Payment / tariff receipt** (Parking) — the parking product renders totals as plain mono rows; formalise if a second product needs it.
- **District drill-down** — the supplied `Xarita` file contains per-district paths that were not imported.

## Using this system

```html
<link rel="stylesheet" href="styles.css">
<script src="_ds_bundle.js"></script>
<script type="text/babel">
  const { Panel, Button, RiskLegend, InteractionTimeline } = window.SentinelSOCDesignSystem_d3364b;
</script>
```

Rules of thumb: build every region as a `Panel`; put exactly one primary violet
action per screen; keep colour out of everything that is not data; reach for a
hairline before a shadow, and for a chamfer before a radius.
