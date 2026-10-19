---
name: GeoSketch Design System
colors:
  surface: '#f8f9ff'
  surface-dim: '#cbdbf5'
  surface-bright: '#f8f9ff'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#eff4ff'
  surface-container: '#e5eeff'
  surface-container-high: '#dce9ff'
  surface-container-highest: '#d3e4fe'
  on-surface: '#0b1c30'
  on-surface-variant: '#434655'
  inverse-surface: '#213145'
  inverse-on-surface: '#eaf1ff'
  outline: '#737686'
  outline-variant: '#c3c6d7'
  surface-tint: '#0053db'
  primary: '#004ac6'
  on-primary: '#ffffff'
  primary-container: '#2563eb'
  on-primary-container: '#eeefff'
  inverse-primary: '#b4c5ff'
  secondary: '#006b5f'
  on-secondary: '#ffffff'
  secondary-container: '#6df5e1'
  on-secondary-container: '#006f64'
  tertiary: '#9d2940'
  on-tertiary: '#ffffff'
  tertiary-container: '#bd4257'
  on-tertiary-container: '#ffeded'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#dbe1ff'
  primary-fixed-dim: '#b4c5ff'
  on-primary-fixed: '#00174b'
  on-primary-fixed-variant: '#003ea8'
  secondary-fixed: '#71f8e4'
  secondary-fixed-dim: '#4fdbc8'
  on-secondary-fixed: '#00201c'
  on-secondary-fixed-variant: '#005048'
  tertiary-fixed: '#ffdadc'
  tertiary-fixed-dim: '#ffb2b9'
  on-tertiary-fixed: '#400010'
  on-tertiary-fixed-variant: '#891933'
  background: '#f8f9ff'
  on-background: '#0b1c30'
  surface-variant: '#d3e4fe'
typography:
  display-hero:
    fontFamily: Inter
    fontSize: 44px
    fontWeight: '700'
    lineHeight: 52px
    letterSpacing: -0.03em
  display-hero-mobile:
    fontFamily: Inter
    fontSize: 32px
    fontWeight: '700'
    lineHeight: 38px
    letterSpacing: -0.02em
  headline-lg:
    fontFamily: Inter
    fontSize: 30px
    fontWeight: '600'
    lineHeight: 38px
    letterSpacing: -0.02em
  headline-md:
    fontFamily: Inter
    fontSize: 22px
    fontWeight: '600'
    lineHeight: 28px
    letterSpacing: -0.015em
  headline-sm:
    fontFamily: Inter
    fontSize: 17px
    fontWeight: '600'
    lineHeight: 24px
    letterSpacing: -0.01em
  body-lg:
    fontFamily: Inter
    fontSize: 16px
    fontWeight: '400'
    lineHeight: 24px
    letterSpacing: -0.005em
  body-md:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 20px
    letterSpacing: 0em
  body-sm:
    fontFamily: Inter
    fontSize: 12px
    fontWeight: '400'
    lineHeight: 16px
    letterSpacing: 0.01em
  telemetry-hero:
    fontFamily: JetBrains Mono
    fontSize: 36px
    fontWeight: '600'
    lineHeight: 40px
    letterSpacing: -0.04em
  telemetry-hero-mobile:
    fontFamily: JetBrains Mono
    fontSize: 26px
    fontWeight: '600'
    lineHeight: 30px
    letterSpacing: -0.03em
  telemetry-md:
    fontFamily: JetBrains Mono
    fontSize: 15px
    fontWeight: '500'
    lineHeight: 20px
    letterSpacing: -0.02em
  telemetry-sm:
    fontFamily: JetBrains Mono
    fontSize: 12px
    fontWeight: '500'
    lineHeight: 16px
    letterSpacing: 0em
  label-caps:
    fontFamily: Inter
    fontSize: 11px
    fontWeight: '600'
    lineHeight: 14px
    letterSpacing: 0.06em
rounded:
  sm: 0.25rem
  DEFAULT: 0.5rem
  md: 0.75rem
  lg: 1rem
  xl: 1.5rem
  full: 9999px
spacing:
  gutter: 1.25rem
  gutter-desktop: 1.5rem
  margin: 1rem
  margin-tablet: 1.5rem
  margin-desktop: 2rem
  space-xs: 0.25rem
  space-sm: 0.5rem
  space-md: 1rem
  space-lg: 1.5rem
  space-xl: 2.5rem
---

## Brand & Style

This design system crafts an airy, luminous, and precision-driven environment engineered specifically for GPS route art, telemetric tracking, and outdoor motion synthesis. The design ethos fuses technical spatial precision with the freedom of outdoor athletics and cartographic creativity. 

### Aesthetic Philosophy
The system rejects heavy dark chrome, dense skeuomorphic instrumentation, and muddy transparencies in favor of a radiant, high-clarity **Modern Outdoor Cartographic** aesthetic. The visual atmosphere feels like natural morning daylight over terrain: expansive, crisp, and weightless. Surfaces breathe through broad margins, micro-borders in soft slate, and delicate atmospheric illumination.

### Core Visual Tenets
- **Radiant Pure-Light Canvas:** UI chrome, data panels, and cartographic overlays live strictly within high-key tonal values. There are no dark control drawers, heavy black navigation bars, or inverted HUDs. Map tiles adopt custom silver-sand, chalk, and pale marine tonalities.
- **Instrumental Tactility:** Micro-interactions feel deliberate, responsive, and calibrated. Interfaces leverage 1px hairpins, subtle mechanical pill badges, and dual-layered soft ambient shadows to convey tangible floating instruments above the geo-canvas.
- **Bi-Systemic Data Dialect:** Expressive vector linework and fluid routes contrast with strict, tabular telemetric figures. Monospace readouts bring aviation-grade precision to pacing, heart rate, cadence, lat/long bearings, and distance milestones.

## Colors

The palette is tuned for razor-sharp legibility across high-glare outdoor displays, studio monitors, and projectors. The baseline interface maintains strict contrast ratios exceeding WCAG AAA standards (7:1) for body text and AA (4.5:1) for telemetric micro-readouts.

### Canvas & Surfaces
- **Atmospheric Canvas Base:** `#F6F8FC` as the global backdrop, accented at the top scroll boundary with subtle radial ambient diffusions of Sky Mist (`#E0F2FE`) and Seafoam Dawn (`#CCFBF1`).
- **Surface Elevation 1 (Cards, Floating Toolbars, Panels):** Pure White `#FFFFFF` bound by a crisp 1px perimeter border in `#E4E9F2`.
- **Surface Elevation 2 (Inputs, Troughs, Data Wells, Inactive Pills):** `#F1F5FB`, providing immediate optical inset without relying on heavy shadows.

### Ink Hierarchy
- **Heading Ink:** `#0F172A` — Deep slate for structural headings, hero metrics, and waypoint identifiers.
- **Body Ink:** `#334155` — Dense charcoal-slate for descriptions, route legends, and tabular labels.
- **Muted Ink / Secondary Metadata:** `#64748B` — Neutralized slate for units of measure, coordinates, and inactive timestamps. Minimum font size is 11px to maintain legibility in all lighting conditions.

### Accents & Cartographic Linework
- **Primary (Sky Command):** `#2563EB` — Main interactive controls, active tool selections, primary track line. Paired with `#DBEAFE` for state washes and focus rims.
- **Secondary (Telemetry Mint):** `#14B8A6` — Elevation deltas, pace segments, and completed trace checkpoints.
- **Route Accent (Solar Coral):** `#FB7185` — Vector drawing cursor, virtual pacer, live GPS beacon, and route anomaly callouts.

### Semantic Status Enclaves
- **Live GPS Signal:** Ink `#16A34A` | Surface `#DCFCE7` | Border `#BBF7D0`
- **Simulated / Demo Mode:** Ink `#7C3AED` | Surface `#EDE9FE` | Border `#DDD6FE`
- **Telemetry Warning:** Ink `#D97706` | Surface `#FEF3C7` | Border `#FDE68A`
- **Hazard / Abort Red:** Ink `#DC2626` | Surface `#FEE2E2` | Border `#FECACA`

## Typography

Typography establishes an unambiguous dichotomy between cartographic UI navigation and real-time instrumental feedback.

### Architectural Rules
- **Inter (Interface & Prose):** Used across structural UI elements, action buttons, dialogues, navigational lists, and narrative route descriptions. Feature settings `cv02`, `cv03`, and `cv04` are activated to maximize distinct glyph legibility during fast scanning.
- **JetBrains Mono (Telemetry & Metrics):** Strictly required for coordinates (`37°46'39.2"N`), elevations (`+1,420m`), timestamps (`02:44:12`), speed meters (`24.8 km/h`), and pacing splits. All figures render as monospaced tabular numerals to eliminate micro-jitter during real-time GPS stream refreshes.
- **Pacing & Readability Limits:** Body and telemetry text must never fall below 11px. All uppercase tokens (`label-caps`) employ `+0.06em` tracking to prevent character collision on high-density displays.

## Layout & Spacing

The interface implements a dual-canvas spatial system: an unrestricted full-bleed interactive map engine underneath, bordered or overlaid by floating modular telemetry hubs and control docks.

### Grid & Breakpoints
- **Desktop (≥ 1280px):** 12-column dynamic flex grid over layout canvas, or fixed 380px floating control sidebar with a 24px inset margin from screen perimeters. Main workspace margins are 32px (`margin-desktop`) with 24px gutters (`gutter-desktop`).
- **Tablet (768px – 1279px):** 8-column layout. Control drawers anchor to the viewport bottom or collapsible floating panels with 24px margins (`margin-tablet`) and 20px gutters (`gutter`).
- **Mobile (≤ 767px):** 4-column layout with 16px margins (`margin`). Operational telemetry consolidates into bottom-docked swipe sheets leaving 65% of the upper screen real estate clear for spatial GPS line generation.

### Spacing Cadence
A base unit of 4px governs all element pacing. Component padding adheres to strict relational pairings:
- Data capsules and small chips utilize `space-xs` (4px) vertical by `space-sm` (8px) horizontal.
- Standard inputs and actions apply `space-sm` (8px) vertical by `space-md` (16px) horizontal.
- Card interiors and metric hubs scale between `space-md` (16px) and `space-lg` (24px).
- Major panel segmentations and widget sections preserve `space-xl` (40px) clearances.

## Elevation & Depth

Visual separation relies on physical surface lift and delicate ambient occlusion rather than harsh boundary lines. Because dark modes are completely excluded, shadows are lightened, tinted with blue-slate, and diffused to simulate morning sky lighting.

### Elevation Architecture
- **Level 0 (Earth Canvas):** Base map engine and root application canvas (`#F6F8FC`). Flush.
- **Level 1 (Docked Tiles & Structural Wells):** Recessed or co-planar surfaces (`#F1F5FB`) with zero shadow, framed exclusively by 1px solid borders in `#E4E9F2`.
- **Level 2 (Active Cards & Overlay Modules):** Surface `#FFFFFF`. Bounded by a crisp 1px `#E4E9F2` border and supported by a soft two-stage ambient shadow:
  - Specular: `0 1px 2px 0 rgba(15, 23, 42, 0.04)`
  - Atmospheric diffusion: `0 8px 24px -4px rgba(15, 23, 42, 0.06)`
- **Level 3 (Floating HUD, Route Tools, Context Modals):** Surface `#FFFFFF` with micro-hairline border `#E2E8F0` and elevated ambient lift:
  - `0 4px 6px -1px rgba(15, 23, 42, 0.05)`
  - `0 16px 36px -6px rgba(15, 23, 42, 0.10)`
- **Level 4 (Toasts & Waypoint Tooltips):** Floating interactive pins. `0 20px 40px -8px rgba(15, 23, 42, 0.12)`.

## Shapes

The geometric signature balances athletic friendliness with navigational precision through consistent progressive radii:

- **Metrics & Content Cards:** 16px to 20px corner radius (`rounded-lg` / `rounded-xl`), creating soft windowing for map projections and charts.
- **Buttons & Form Fields:** Strictly 12px radius, yielding balanced, tactile press targets that preserve geometric definition.
- **Status Badges, Steppers, & GPS Toggles:** Full pill radius (`rounded-full` / 9999px) to maintain immediate semiotic distinction against rectangular data panels.
- **Icon Enclosures & Micro Wells:** 8px radius (`rounded-md`), framing 18px–20px Lucide stroke icons.

## Components

### Buttons & Interactive Triggers
- **Primary Action (Start Trace, Commit Route):** Background `#2563EB`, text `#FFFFFF`, borderless, 12px border radius, font `Inter` 14px weight 600. Hover: `#1D4ED8`. Active state: subtle scale down `0.98`. Focus ring: 3px `#DBEAFE` with 1px white offset.
- **Secondary Action (Export GPX, Recenter):** Background `#FFFFFF`, text `#334155`, border 1px solid `#E4E9F2`, 12px border radius. Hover: background `#F1F5FB`, text `#0F172A`, border `#CBD5E1`.
- **Destructive Action (Clear Path):** Background `#FEE2E2`, text `#DC2626`, 12px border radius. Hover: `#FCDAD7`.

### Status Indicators & Badges
- Continuous rounded-pill shape (height 24px, padding 2px 10px).
- **Live Hardware Feed:** `#DCFCE7` background, `#16A34A` text, 1px border `#BBF7D0`. Features a 6px pulsing dot in `#16A34A`.
- **Demo / Synthetic Simulation:** `#EDE9FE` background, `#7C3AED` text, 1px border `#DDD6FE`. Features an un-pulsed hollow diamond icon in `#7C3AED`.
- **GPS Fix Quality:** Numeric pill rendering satellite lock count via `JetBrains Mono` 11px (e.g., `SAT: 14`).

### Input Fields & Search Bars
- **Container:** Height 44px, surface `#F1F5FB`, 12px radius, border 1px solid transparent.
- **Focus Transition:** Surface transitions to `#FFFFFF`, border shifts to `#2563EB`, paired with a 3px halo in `#DBEAFE`.
- **Wayfinding Autocomplete:** Surface `#FFFFFF`, floating elevation level 3, row heights of 40px with inline Lucide pin vectors in `#64748B`.

### Telemetry Cards & Metric Blocks
- Pure white `#FFFFFF` shell, 18px corner radius, 1px `#E4E9F2` border, level 2 ambient shadow.
- Interior anatomy: Top-aligned category label (`label-caps` in `#64748B`), centered prominent numeric readout (`telemetry-hero` in `#0F172A`), bottom trend delta badge with micro directional arrow (`#16A34A` or `#DC2626`).

### Checkboxes & Segmented Controls
- **Checkboxes:** 18px square with 6px border radius. Border 1.5px solid `#CBD5E1`. Checked state: background `#2563EB`, checkmark `#FFFFFF` with 2px stroke width.
- **Mode Switcher (Live Draw / Waypoint Snap / Freeform):** Contained pill segment in `#F1F5FB`, internal sliding selection tablet in `#FFFFFF` with 1px `#E4E9F2` border and level 1 shadow. Active label `#0F172A`, inactive `#64748B`.

### Map Layer Chrome & Tool Overlays
- Vertical floating dock positioned on the right map margin: pure white `#FFFFFF` enclosure, 12px radius, dividing dividers 1px `#E4E9F2`. Action buttons 40x40px with stroke-based navigation icons in `#334155` at 1.75px stroke width.