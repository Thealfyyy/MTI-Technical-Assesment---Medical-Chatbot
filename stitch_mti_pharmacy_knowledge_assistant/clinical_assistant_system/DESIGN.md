---
name: Clinical Assistant System
colors:
  surface: '#f8f9ff'
  surface-dim: '#cddbf4'
  surface-bright: '#f8f9ff'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#eff3ff'
  surface-container: '#e6eeff'
  surface-container-high: '#dde9ff'
  surface-container-highest: '#d5e3fd'
  on-surface: '#0e1c2f'
  on-surface-variant: '#434751'
  inverse-surface: '#233145'
  inverse-on-surface: '#ebf1ff'
  outline: '#737783'
  outline-variant: '#c3c6d3'
  surface-tint: '#2d5cad'
  primary: '#003d89'
  on-primary: '#ffffff'
  primary-container: '#2455a6'
  on-primary-container: '#b9ceff'
  inverse-primary: '#aec6ff'
  secondary: '#585f68'
  on-secondary: '#ffffff'
  secondary-container: '#dce3ee'
  on-secondary-container: '#5e656e'
  tertiary: '#693000'
  on-tertiary: '#ffffff'
  tertiary-container: '#8c4300'
  on-tertiary-container: '#ffc099'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#d8e2ff'
  primary-fixed-dim: '#aec6ff'
  on-primary-fixed: '#001a42'
  on-primary-fixed-variant: '#054394'
  secondary-fixed: '#dce3ee'
  secondary-fixed-dim: '#c0c7d2'
  on-secondary-fixed: '#151c24'
  on-secondary-fixed-variant: '#404750'
  tertiary-fixed: '#ffdbc7'
  tertiary-fixed-dim: '#ffb688'
  on-tertiary-fixed: '#311300'
  on-tertiary-fixed-variant: '#733600'
  background: '#f8f9ff'
  on-background: '#0e1c2f'
  surface-variant: '#d5e3fd'
typography:
  display:
    fontFamily: Inter
    fontSize: 36px
    fontWeight: '600'
    lineHeight: 44px
    letterSpacing: -0.02em
  headline-lg:
    fontFamily: Inter
    fontSize: 28px
    fontWeight: '600'
    lineHeight: 36px
    letterSpacing: -0.02em
  headline-lg-mobile:
    fontFamily: Inter
    fontSize: 24px
    fontWeight: '600'
    lineHeight: 32px
    letterSpacing: -0.01em
  headline-md:
    fontFamily: Inter
    fontSize: 22px
    fontWeight: '600'
    lineHeight: 28px
    letterSpacing: -0.01em
  headline-sm:
    fontFamily: Inter
    fontSize: 18px
    fontWeight: '600'
    lineHeight: 24px
    letterSpacing: -0.005em
  body-lg:
    fontFamily: Inter
    fontSize: 16px
    fontWeight: '400'
    lineHeight: 26px
    letterSpacing: 0em
  body-md:
    fontFamily: Inter
    fontSize: 15px
    fontWeight: '400'
    lineHeight: 24px
    letterSpacing: 0em
  body-sm:
    fontFamily: Inter
    fontSize: 13px
    fontWeight: '400'
    lineHeight: 20px
    letterSpacing: 0em
  label-md:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '500'
    lineHeight: 20px
    letterSpacing: 0em
  label-sm:
    fontFamily: Inter
    fontSize: 12px
    fontWeight: '500'
    lineHeight: 16px
    letterSpacing: 0.01em
  tabular-data:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 20px
    letterSpacing: 0em
rounded:
  sm: 0.25rem
  DEFAULT: 0.5rem
  md: 0.75rem
  lg: 1rem
  xl: 1.5rem
  full: 9999px
spacing:
  gutter: 1rem
  gutter-desktop: 1.5rem
  margin: 1rem
  margin-tablet: 1.5rem
  margin-desktop: 2rem
  space-xs: 0.25rem
  space-sm: 0.5rem
  space-md: 1rem
  space-lg: 1.5rem
  space-xl: 2rem
---

## Brand & Style

This design system delivers a high-trust, calm, and clinical workspace tailored for pharmacy staff and healthcare professionals interacting with bilingual pharmaceutical knowledge bases. The operational environment demands instantaneous clarity, zero ambiguity, and minimal visual fatigue during long dispensary shifts.

The aesthetic philosophy is an exact blend of modern clinical minimalism and Swiss-style precision:
- **Visual Stance:** Neutrals-first, rigorous structural hierarchy, and functional restraint. Visual elements never compete with safety-critical drug interaction data, dosage guidelines, or contraindications.
- **Atmospheric Quality:** Grounded and serene. The interface uses solid structural surfaces over decorative flourishes, avoiding heavy drop shadows or vibrant saturated fills in favor of clean hairlines and balanced margins.
- **Bilingual Symmetry:** Tailored natively for dual English (LTR) and Arabic (RTL) reading patterns. Layouts, visual flow, and components mirror naturally while preserving semantic status patterns and tabular data readability across both writing systems.

## Colors

The palette operates under a strict neutrals-first hierarchy with clinical blue functioning as the single primary accent. Color carries structural meaning and diagnostic feedback rather than ornamental decoration.

### Core Roles
- **Primary (`#2455A6`):** Reserved for primary interactive triggers, active tab indicators, and focal search elements. States transition intentionally to **Primary Hover (`#1D478A`)**.
- **Soft Accent (`#EAF1FC`):** Used strictly for subtle background selection states, pill container fills, active navigation items, and highlighted critical text spans.
- **Page Canvas (`#F6F8FB`):** A cool, low-strain tinted white base that softens screen glare under clinical dispensary lighting.
- **Surface (`#FFFFFF`):** High-clarity white utilized exclusively for cards, dialog sheets, popovers, and tables.
- **Hairline Border (`#DCE4EF`):** Subtle structural divider defining containers and interactive perimeters without harsh visual cuts.
- **Ink Primary (`#172538`):** Deep slate ink providing WCAG AAA-compliant text contrast for high-stakes medical copy.
- **Muted Text (`#66758A`):** Low-contrast secondary text for metadata, timestamps, formulation codes, and field labels.

### Semantic Alerts
Diagnostic feedback uses distinct dual-signal pairing (text, background, and icon):
- **Success (`#19734E`):** Validated dosages, completed verifications, and available inventory.
- **Warning Text (`#81540B`) on Warning Fill (`#FFF4DF`):** Interaction cautions, dosage adjustments, and clinical alerts.
- **Danger (`#A63A35`):** Severe contraindications, boxed warnings, and allergy blocks.

## Typography

The type system is engineered around dual-script legibility: **Inter** for Latin characters and **IBM Plex Sans Arabic** for Arabic script. 

### Font Rules & Pairings
- Latin body and headlines render in `Inter`. Arabic text maps automatically to `IBM Plex Sans Arabic` while inheriting the size, weight, and line-height scale defined.
- Body text is calibrated to 15px (`body-md`) and 16px (`body-lg`) set with a 1.6 line-height ratio (`1.6em` / `24-26px`) to ensure prolonged reading comfort and clear character separation for pharmaceutical terminology.
- Headings employ tight tracking (`-0.01em` to `-0.02em`) on Latin scripts to maintain structural unity; Arabic headings preserve native proportional glyph spacing without tracking compression.

### Numerical and Table Formatting
- Numerical indicators, strengths, dosages, batch numbers, and ATC codes must use OpenType tabular lining figures (`font-variant-numeric: tabular-nums;`) inside data lists and tables to ensure vertical alignment across dynamic queries.

## Layout & Spacing

The layout is built upon an 8px modular baseline system that governs all layout positions, component internal padding, and grid tracks.

### Grid & Composition
- **Desktop (1024px+):** 12-column responsive fluid grid. Margins are fixed at 32px (`2rem`), with column gutters set to 24px (`1.5rem`).
- **Tablet (768px - 1023px):** 8-column layout with 24px (`1.5rem`) margins and 16px (`1rem`) gutters. Side panels collapse into layered sheets.
- **Mobile (320px - 767px):** 4-column layout with 16px (`1rem`) outer margins and 16px (`1rem`) gutters.

### Component Spacing Rhythm
- **Cards:** Content cards must feature 24px (`1.5rem`) of internal padding and maintain a strict 16px (`1rem`) separation gap between adjacent cards or grid units.
- **Form Groups & Inputs:** Vertical field gaps standardise on 16px (`space-md`), with tight label-to-input distancing set to 6px-8px (`space-sm`).
- **RTL Fluidity:** Structural layout grids invert automatically via CSS logical properties (`margin-inline-start`, `padding-inline-end`). Horizontal padding values remain perfectly identical across script direction changes.

## Elevation & Depth

To preserve clinical focus and reduce visual noise, this design system operates with minimal layering and avoids heavy stacking shadows.

### Border Precision
- Interfaces rely fundamentally on 1px hairline borders (`#DCE4EF`) to delineate content modules, navigation bars, and inputs against the `#FFFFFF` and `#F6F8FB` planes.

### Single Elevation Level
- Only one soft, diffused shadow is permitted in the system, reserved exclusively for floating surfaces (dropdown menus, popover tooltips, modal dialogs, and active cards):
  - `box-shadow: 0 4px 16px -2px rgba(23, 37, 56, 0.06), 0 2px 6px -1px rgba(23, 37, 56, 0.03);`
- Flat cards maintain zero shadow elevation at rest, floating strictly through `#DCE4EF` hairline isolation. On hover or active selection, an optional hairline shift to primary `#2455A6` or an ambient tint is applied.

## Shapes

The geometric framework balances humanized soft curves with disciplined clinical utility:

- **Cards & Data Panels:** 16px corner radius creates an approachable boundary for large grouped knowledge summaries and clinical monographs.
- **Interactive Controls (Inputs, Buttons, Dropdowns):** 10px corner radius provides an ergonomic, modern profile that defines discrete touchpoints without resembling toy-like rounded pills.
- **Status Pills, Chips & Tags:** 999px fully rounded pill radius differentiates categorizations, active state badges, and warning labels from actionable buttons.

## Components

### Buttons
- **Primary:** Solid `#2455A6` background, `#FFFFFF` text, 10px radius, minimum 44px height. Hover state: `#1D478A`.
- **Secondary / Ghost:** Transparent background with 1px `#DCE4EF` border, `#172538` text. Hover state: `#EAF1FC` background with `#2455A6` text and border.
- **Touch Target:** Minimum dimension of 44px x 44px across desktop and mobile.

### Input Fields & Search Bars
- **Surface:** `#FFFFFF` background, 10px radius, 1px `#DCE4EF` border, minimum 44px height, horizontal padding 14px.
- **Text:** 15px `Inter` / `IBM Plex Sans Arabic`, `#172538` active text, `#66758A` placeholder.
- **Focus:** 2px high-contrast focus ring in `#2455A6` with a 2px offset (`box-shadow: 0 0 0 2px #FFFFFF, 0 0 0 4px #2455A6;`).
- **Bilingual Icons:** Search and clear icons flip positions dynamically according to text direction (`dir="rtl"` vs `dir="ltr"`).

### Cards & Drug Monographs
- **Structure:** 16px corner radius, `#FFFFFF` fill, 1px `#DCE4EF` perimeter border, 24px internal padding.
- **Header Section:** Dedicated title row with 18px bold heading and inline status pill. Separated from card body by a 1px `#DCE4EF` divider if content exceeds 4 data fields.

### Status Pills & Badges
- **Shape:** 999px rounded pill, padding 4px 12px.
- **Typography:** 12px bold (`label-sm`).
- **Multi-Signal Requirement:** Status is never communicated by color alone. Every badge pairs an unambiguous label with an identifying geometric icon:
  - *Standard:* `#EAF1FC` background, `#2455A6` text.
  - *Success:* `#E8F5EE` background, `#19734E` text.
  - *Warning:* `#FFF4DF` background, `#81540B` text.
  - *Contraindication:* `#FDF0ED` background, `#A63A35` text.

### Data Lists & Tables
- **Rows:** Minimum height 48px, hairline border-bottom `#DCE4EF`.
- **Headers:** `#F6F8FB` surface, 13px uppercase label, `#66758A` text color.
- **Numerals:** Configured with `font-variant-numeric: tabular-nums` for precise alignment of concentrations, dosages, and package counts.

### Checkboxes & Radios
- **Dimensions:** 20px x 20px box with 44px interactive hit area.
- **State:** Unchecked has 1.5px `#DCE4EF` border; checked fills with `#2455A6` carrying a crisp white indicator glyph. Focus outlines mirror the 2px blue ring.