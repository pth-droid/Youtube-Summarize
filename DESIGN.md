---
name: Distill
description: A local learning workspace drawn as a night atlas. Work floats on sheets over a topographic map, and every job is a route.
colors:
  ground-night: "#0e1416"
  ground-day: "#e2e8e5"
  sheet-night: "#172023"
  sheet-day: "#ffffff"
  sheet-inset-night: "#10171a"
  sheet-inset-day: "#f1f4f2"
  raise-night: "#202a2d"
  raise-day: "#e8edea"
  ink-night: "#eef3f1"
  ink-day: "#12191b"
  muted-night: "#9aaca7"
  muted-day: "#56635f"
  on-map-night: "#f3f6f5"
  on-map-muted-day: "#45524f"
  line-night: "rgb(255 255 255 / .08)"
  line-strong-night: "rgb(255 255 255 / .15)"
  line-day: "rgb(15 30 28 / .09)"
  line-strong-day: "rgb(15 30 28 / .17)"
  glass-night: "rgb(26 36 39 / .55)"
  glass-hover-night: "rgb(52 66 70 / .7)"
  glass-day: "rgb(255 255 255 / .58)"
  glass-hover-day: "rgb(255 255 255 / .9)"
  contour-night: "rgb(214 232 226 / .085)"
  contour-day: "rgb(22 48 44 / .12)"
  pool-teal-night: "rgb(42 116 120 / .42)"
  pool-amber-night: "rgb(245 165 36 / .11)"
  pin-white: "#f7faf9"
  pin-ink: "#0f1618"
  primary-hover-day: "#263134"
  amber: "#f5a524"
  on-amber: "#1d1304"
  amber-ink-night: "#f7b13a"
  amber-ink-day: "#975700"
  amber-soft: "rgb(245 165 36 / .13)"
  amber-line-night: "rgb(245 165 36 / .6)"
  amber-line-day: "rgb(214 132 6 / .7)"
  good-night: "#63c792"
  good-day: "#1c7f4d"
  bad-night: "#ff8a7a"
  bad-day: "#b8352a"
  cover-teal: "#2a6a69"
  cover-moss: "#56733c"
  cover-blue: "#335a8a"
  cover-ochre: "#9a6a1c"
  cover-clay: "#8a4a36"
  cover-violet: "#4f4a80"
typography:
  headline:
    fontFamily: "Be Vietnam Pro, ui-sans-serif, system-ui, Segoe UI, sans-serif"
    fontSize: "1.75rem"
    fontWeight: 600
    lineHeight: 1.2
    letterSpacing: "-0.022em"
  title-lg:
    fontFamily: "Be Vietnam Pro, ui-sans-serif, system-ui, Segoe UI, sans-serif"
    fontSize: "1.25rem"
    fontWeight: 600
    lineHeight: 1.35
    letterSpacing: "-0.012em"
  title:
    fontFamily: "Be Vietnam Pro, ui-sans-serif, system-ui, Segoe UI, sans-serif"
    fontSize: "1.0625rem"
    fontWeight: 600
    lineHeight: 1.35
    letterSpacing: "-0.01em"
  body:
    fontFamily: "Be Vietnam Pro, ui-sans-serif, system-ui, Segoe UI, sans-serif"
    fontSize: "0.9375rem"
    fontWeight: 400
    lineHeight: 1.55
  body-sm:
    fontFamily: "Be Vietnam Pro, ui-sans-serif, system-ui, Segoe UI, sans-serif"
    fontSize: "0.875rem"
    fontWeight: 400
    lineHeight: 1.55
  label:
    fontFamily: "Be Vietnam Pro, ui-sans-serif, system-ui, Segoe UI, sans-serif"
    fontSize: "0.8125rem"
    fontWeight: 500
    lineHeight: 1.4
  meta:
    fontFamily: "Be Vietnam Pro, ui-sans-serif, system-ui, Segoe UI, sans-serif"
    fontSize: "0.75rem"
    fontWeight: 400
    lineHeight: 1.4
  micro:
    fontFamily: "Be Vietnam Pro, ui-sans-serif, system-ui, Segoe UI, sans-serif"
    fontSize: "0.6875rem"
    fontWeight: 500
    lineHeight: 1.2
    fontFeature: "\"tnum\""
  mono:
    fontFamily: "ui-monospace, Cascadia Mono, Consolas, monospace"
    fontSize: "0.75rem"
    fontWeight: 400
    lineHeight: 1.5
rounded:
  sheet: "28px"
  card: "26px"
  panel: "24px"
  tile: "20px"
  cover: "19px"
  look: "16px"
  field: "14px"
  swatch: "11px"
  pill: "999px"
  round: "50%"
spacing:
  xxs: "4px"
  xs: "8px"
  sm: "12px"
  md: "16px"
  lg: "20px"
  xl: "24px"
  sheet: "28px"
  rail: "88px"
  float: "16px"
components:
  button-primary:
    backgroundColor: "{colors.pin-white}"
    textColor: "{colors.pin-ink}"
    typography: "{typography.body-sm}"
    rounded: "{rounded.pill}"
    padding: "0 20px"
    height: "44px"
  button-primary-day:
    backgroundColor: "{colors.ink-day}"
    textColor: "{colors.sheet-day}"
    rounded: "{rounded.pill}"
    padding: "0 20px"
    height: "44px"
  button-primary-day-hover:
    backgroundColor: "{colors.primary-hover-day}"
  button-secondary:
    backgroundColor: "{colors.sheet-inset-night}"
    textColor: "{colors.ink-night}"
    rounded: "{rounded.pill}"
    padding: "0 20px"
    height: "44px"
  button-secondary-hover:
    backgroundColor: "{colors.raise-night}"
  button-quiet:
    backgroundColor: "transparent"
    textColor: "{colors.muted-night}"
    rounded: "{rounded.pill}"
    padding: "0 12px"
    height: "44px"
  button-glass:
    backgroundColor: "{colors.glass-night}"
    textColor: "{colors.on-map-night}"
    rounded: "{rounded.pill}"
    padding: "0 20px"
    height: "44px"
  orb:
    backgroundColor: "{colors.glass-night}"
    textColor: "{colors.on-map-night}"
    rounded: "{rounded.round}"
    size: "44px"
  nav-pin-active:
    backgroundColor: "{colors.pin-white}"
    textColor: "{colors.pin-ink}"
    rounded: "{rounded.round}"
    size: "44px"
  count-badge:
    backgroundColor: "{colors.amber}"
    textColor: "{colors.on-amber}"
    typography: "{typography.micro}"
    rounded: "{rounded.pill}"
    height: "20px"
  sheet:
    backgroundColor: "{colors.sheet-night}"
    textColor: "{colors.ink-night}"
    rounded: "{rounded.sheet}"
    padding: "28px"
  page-card:
    backgroundColor: "{colors.sheet-night}"
    rounded: "{rounded.card}"
    padding: "8px"
  field:
    backgroundColor: "{colors.sheet-inset-night}"
    textColor: "{colors.ink-night}"
    rounded: "{rounded.field}"
    padding: "11px 14px"
    height: "46px"
  link-field:
    backgroundColor: "{colors.sheet-inset-night}"
    rounded: "{rounded.pill}"
    padding: "0 260px 0 22px"
    height: "64px"
  glass-field:
    backgroundColor: "{colors.glass-night}"
    textColor: "{colors.on-map-night}"
    rounded: "{rounded.pill}"
    padding: "0 18px"
    height: "52px"
  segmented-pressed:
    backgroundColor: "{colors.amber}"
    textColor: "{colors.on-amber}"
    rounded: "{rounded.pill}"
    padding: "0 15px"
    height: "38px"
  chip:
    backgroundColor: "{colors.sheet-inset-night}"
    textColor: "{colors.ink-night}"
    typography: "{typography.label}"
    rounded: "{rounded.pill}"
    padding: "6px 12px"
  route-pill:
    backgroundColor: "{colors.amber-soft}"
    textColor: "{colors.amber-ink-night}"
    typography: "{typography.label}"
    rounded: "{rounded.pill}"
    padding: "6px 14px 6px 10px"
  route-pill-arrived:
    backgroundColor: "{colors.amber}"
    textColor: "{colors.on-amber}"
---

# Design System: Distill

## Overview

**Creative North Star: "The Learning Atlas"**

The workspace is a map of what the owner is learning. A dark topographic ground fills the window: a generated contour sheet (`terrain.svg`, used as a CSS mask) over two soft pools of light, teal high on the right and amber low on the left. Work never sits flat on that ground. It floats on it as graphite sheets at night and white sheets by day, and the few controls that touch the map directly (the rail, theme and help orbs, library search, recent stops, job rows) are frosted glass, because the map scrolls beneath them. Every job is a route: stops on a curved line, the live leg flowing in amber, the destination pin filling when the page is ready.

Density is calm and operational. One family (Be Vietnam Pro, 400 to 700) carries every word, set in a short ramp from 28px view headings down to 11px tags. One signal colour, amber, marks routes, the live stop, the pressed choice and count badges; everything else is ink, graphite and translucent white. Primary actions are pills in the pin colour (white at night, ink by day), so amber stays free to mean "here, now, chosen".

The world rejects the grey sidebar beside a white grid of cards and the old forest-green sidebar it replaced. It lands as the pinned Dribbble reference (Nixtio, "Bike Rental & Navigation App UI Design") asked: an immersive map canvas, round frosted controls, floating cards and amber route lines.

**Key Characteristics:**
- A fixed map ground (two radial pools plus a masked contour layer) behind everything, in both themes.
- Floating sheets with a 28px radius and a shadow that follows the shape; one hero sheet grows a lobe.
- Frosted glass only where a control floats directly on the map.
- White pins with ink icons at night, inverted by day; amber is the single signal.
- Routes as the signature: curved legs, stops, a stops-left pill, a destination pin.
- One family, authored 1.6px stroke icons from a single sprite.

## Colors

A two-theme palette of map ground, graphite or white sheets, frosted glass and one amber signal. Both themes share the same roles; theme.js sets `data-theme` on the root before paint, and night is the default.

### Primary
- **Route Amber** (`amber`): the only signal colour. Route lines and stops, the live leg, the live and waiting job dots, the arrived destination pin, the pressed segmented tab, the selected format option's icon and radio, selected look borders, count badges, focus rings, text selection and the caret. It is never a decorative fill and never the primary action at rest.
- **Amber Ink** (`amber-ink-night` / `amber-ink-day`): amber that has to be read as text (links, live and warning badges, the route pill's words). By day it drops to a deep brown-amber so it holds contrast on white.
- **Amber Soft and Amber Line** (`amber-soft`, `amber-line-night` / `amber-line-day`): the wash and border for chosen tiles, the approval panel and the focus halo on fields (a 4px soft ring).

### Secondary
- **Pin White / Pin Ink** (`pin-white`, `pin-ink`): the pin pair. At night the active nav pin, the brand pin, done stops and the primary button are white with ink icons; by day the pair inverts (ink pins, white icons, `ink-day` primary with `primary-hover-day` on hover). Cover pins stay white in both themes because covers are always dark.

### Tertiary
- **Survey Tints** (`cover-teal`, `cover-moss`, `cover-blue`, `cover-ochre`, `cover-clay`, `cover-violet`): six cover gradients, each running from the listed tint to a near-black of the same hue at 155deg, with a white highlight pool and the terrain mask at 34% white over it. A source's tint and the offsets of its patch of terrain come from a hash of its id, so a cover is stable and never shared by chance.

### Neutral
- **Night Ground / Day Survey** (`ground-night`, `ground-day`): the map itself. Night is a near-black blue-green; day is a pale survey green-grey.
- **Contour and Pools** (`contour-night`, `contour-day`, `pool-teal-night`, `pool-amber-night`): the contour lines are pale at 8.5% at night and ink at 12% by day; the teal and amber pools grow to 50% and 20% opacity by day.
- **Graphite Sheet / White Sheet** (`sheet-night`, `sheet-day`): every floating surface: sheets, cards, the lobe, dialogs, notices, the help card, tooltips.
- **Sheet Inset** (`sheet-inset-night`, `sheet-inset-day`): fields, choice tiles, chips, look cards, callouts and secondary buttons inside a sheet.
- **Raise** (`raise-night`, `raise-day`): round icon wells and the secondary button's hover.
- **Ink / Muted** (`ink-*`, `muted-*`): text on sheets. **On-map** (`on-map-night`, `on-map-muted-day`): text set directly on the ground or on glass (view headings, ledes, rail labels, recent titles). Night on-map muted is on-map white at 70%.
- **Lines** (`line-*`, `line-strong-*`): hairlines and field borders, translucent so they sit on either sheet tone.
- **Glass** (`glass-*`, `glass-hover-*`): frosted controls on the map, with a 1px glass line (white at 13% at night, 85% by day).
- **Good / Bad** (`good-*`, `bad-*`): status only, each with a soft wash at 9 to 14%. Badges always pair the colour with a word.

### Named Rules
**The One Signal Rule.** Amber means here, now or chosen: a route, the live stop, a pressed choice, a count, focus. If an element is amber and none of those, it is wrong.

**The Pin Colour Rule.** The primary action wears the pin colour, white at night and ink by day. Amber fills a button only where the button sits on a pin-coloured surface (the Settings save bar), so it still reads as the one thing to press.

**The Glass Earns Its Place Rule.** Frosted glass (blur 18px, saturate 1.4) appears only on controls that float directly over the map. Inside a sheet, surfaces are solid.

## Typography

**Display Font:** none; the workspace has no display face.
**Body Font:** Be Vietnam Pro (with ui-sans-serif, system-ui, Segoe UI, sans-serif), self-hosted WOFF at 400, 500, 600 and 700, subset to Latin and Vietnamese.
**Label/Mono Font:** the system monospace stack, only for URLs, logs, hex inputs, storage paths and the share command.

**Character:** one humanist grotesque with full Vietnamese diacritics, carrying hierarchy through weight and a tight ramp rather than a second face. Headings tighten their tracking slightly; nothing is set in capitals.

### Hierarchy
- **Headline** (600, 1.75rem, 1.2, -0.022em): the view heading on the map ("What do you want to make?", "Your learning library"), in on-map colour. 1.5rem below 640px.
- **Title Large** (600, 1.25rem, 1.35, -0.012em): job detail, Settings section and dialog headings. The empty state uses 1.375rem.
- **Title** (600, 1.0625rem, 1.35, -0.01em): library card titles (two lines, clamped), the approval heading, connection editor heading. 1rem for tool rows, subheads and the selected stage.
- **Body** (400, 0.9375rem, 1.55): the base size and the lede under a view heading. Ledes and help text cap near 66 to 72ch.
- **Body Small** (400 or 600, 0.875rem): buttons (600), notices, callouts, disclosure summaries (500).
- **Label** (500, 0.8125rem): field labels, hints, segmented tabs, chips, route pill (600), look names (600).
- **Meta** (400 to 600, 0.75rem): card meta, recent meta, stop names, rail brand name, badges (500).
- **Micro** (500 to 700, 0.6875rem, tabular figures for counts): count badges (700), cover tags, lobe stop names, default tags.

### Named Rules
**The One Family Rule.** Be Vietnam Pro sets every word of the workspace. Bricolage Grotesque is served only so the maroon slide look can preview its own type; it never sets workspace text.

**The Weight Not Case Rule.** Hierarchy is weight (400, 500, 600, 700) and a short size ramp. No uppercase labels, no letter-spaced captions, no small text above a heading.

## Layout

The page is a fixed map with floating furniture. On desktop a glass rail, 88px wide, floats 16px off the left, top and bottom edges: the brand pin, a frosted capsule of four labelled nav pins, and theme and help orbs at its foot. Main content starts after the rail plus 56px, pads 36px 40px 28px and caps at 1640px.

- **Create:** the hero sheet (up to 780px) and, at 1280px and wider, a 240 to 300px Recent column 44px to its right. Below 1280px Recent moves under the sheet as a wrapping grid and its dashed trail hides.
- **Library:** glass search (to 520px) and filter on the map, then an auto-fill grid of cards at a 290px minimum with 20px gaps.
- **Processing:** a 320px column of glass job rows beside the job sheet (260px below 1100px, stacked below 900px).
- **Settings:** a 220px sticky glass section rail beside one sheet at a time (to 880px). Below 1100px the rail becomes a horizontal scrolling pill row.
- **Look editor:** a 340 to 400px controls sheet beside a sticky preview stage; below 1280px the preview moves above the controls.
- **Reader:** a floating header row over a 24px-radius frame that fills the viewport less 132px.

Rhythm runs on a 4px base, mostly 8, 12, 16, 20, 24 and 28px; sheets pad 28px (20px 18px below 640px). View heads sit 28px above their content.

**Rail to dock (below 900px).** The rail splits: brand, theme and help become a top row, and the nav capsule becomes a fixed dock 12px off the bottom and sides (plus the safe-area inset), with pins at 40px. Main pads 20px 16px and leaves 112px plus the inset at the foot for the dock. Orb tooltips are dropped, and the help card pins to the top right.

**Phones (below 640px).** The link field drops to 56px and its Create button moves below it at full width; format options lose their descriptions; source tabs share one row without icons; the lobe narrows to fit and, with five stops, shows only its route; field pairs and card grids go to one column.

## Elevation & Depth

Depth is the map: everything sits on one fixed ground, and sheets are lifted off it with long, soft shadows that read as altitude, not borders. Glass controls carry a shorter shadow. There are no hard offset shadows and no outlines-as-depth. A lobed sheet uses `filter: drop-shadow` instead of `box-shadow`, so the shadow follows the sheet and its tab as one shape.

### Shadow Vocabulary
- **Sheet, night** (`inset 0 1px 0 rgb(255 255 255 / .05), 0 28px 60px -20px rgb(0 0 0 / .7), 0 2px 8px rgb(0 0 0 / .25)`): sheets, cards, dialogs, notices, the reader frame. The 1px inner highlight is the top edge catching light.
- **Sheet, day** (`0 28px 60px -24px rgb(22 50 46 / .32), 0 2px 6px rgb(22 50 46 / .08)`): the same role in a green-tinted shadow.
- **Shape drop** (night `drop-shadow(0 24px 30px rgb(0 0 0 / .42)) drop-shadow(0 2px 4px rgb(0 0 0 / .3))`; day `drop-shadow(0 22px 28px rgb(22 50 46 / .17)) drop-shadow(0 2px 3px rgb(22 50 46 / .08))`): only for lobed sheets.
- **Glass** (night `0 12px 30px -12px rgb(0 0 0 / .55)`; day `0 12px 30px -14px rgb(20 45 42 / .35)`): rail, orbs, glass fields and rows, tooltips, pins.
- **Pin lift** (`0 6px 16px -6px rgb(0 0 0 / .45)`): an active nav pin or a cover pin standing off its surface.
- **Primary button** (`0 8px 20px -10px rgb(0 0 0 / .6)`): the pill's small cast shadow.
- **Save bar** (`0 22px 44px -16px rgb(0 0 0 / .6)`): the sticky Settings save bar.

### Named Rules
**The Shadow Follows The Shape Rule.** A sheet with a lobe drops its box-shadow and takes the shape drop, so the tab and the concave corner cast one continuous shadow.

**The Map Is Fixed Rule.** The ground, pools and contours are `position: fixed` behind all content; content scrolls over the map, never the map over itself.

## Shapes

Corners are generous and nested: a 28px sheet holds 20px tiles, which hold 14px fields; a 26px library card holds a 19px cover, so the inner radius equals the outer less the padding. Anything you press directly is a pill (999px) or a circle: buttons, chips, tabs, badges, the link field, glass fields, the dock capsule (44px radius on the rail, 32px as the dock), nav pins, orbs, icon wells. Look swatches are small slides at 16:9 with an 11px radius inside a 16px look option.

The lobe is the one silhouette of its own: the hero sheet's bottom-right corner goes square, and a tab (360px wide, 420 or 500px for four or five stops) hangs from it with a 28px radius on its two lower corners. A 28px concave fillet, drawn as a radial gradient in the sheet colour, joins the tab to the sheet's lower edge, so sheet and tab read as one piece of paper.

Icons are one inline SVG sprite of authored 1.6px strokes with round caps and joins, 18px by default (21px in nav pins, 17px in buttons). Stroke chevrons, checks, info and alert marks are data-URI masks coloured by `background`, so one shape serves both themes.

## Components

### Buttons
Pills that lift slightly and press down.
- **Shape:** full pill (999px), 44px tall, 20px sides, 0.875rem at 600, 8px icon gap. Card buttons shrink to 40px; connection actions to 38px.
- **Primary:** the pin colour (white with ink text at night, ink with white text by day) and a small cast shadow; hover goes to pure white at night, to `primary-hover-day` by day.
- **Secondary:** sheet inset with a strong hairline; hover to raise.
- **Quiet:** transparent, muted text, 12px sides; hover fills with sheet inset and ink.
- **Glass:** frosted, on-map text, used only on the map (Recent's "Open library").
- **Danger:** bad-soft wash with bad text.
- **Press:** scale 0.97 on active. Disabled at 55% opacity with a not-allowed cursor.

### Chips and badges
- **Chips** (saved defaults under the link field): sheet-inset pills with a hairline, a micro muted label and a label-size value, baseline aligned.
- **Badges:** pill, sheet-inset, 0.75rem at 500, a 6px dot in the current colour before the word. Ok uses the good wash, live and warning use amber soft with amber ink (the live dot pulses at 1.6s), error uses the bad wash. Empty badges hide. In job rows the badge drops its dot, because the row's own dot carries the state.
- **Count badges:** amber, 20px tall, 0.6875rem at 700 with tabular figures, pinned top right of a nav pin with a 2px dark ring.
- **Cover tags:** dark frosted pills (blur 8px) on covers; the amber variant marks a deck.

### Cards / Containers
- **Sheet:** graphite or white, 28px radius, 28px padding, sheet shadow. Settings shows one sheet at a time, each rising 8px on entry.
- **Library card:** the whole card opens its page or deck (its delete and open buttons keep their own jobs); 26px radius, 8px padding, min 330px tall; a 140px terrain cover with a white round cover pin (40px) bottom left and tags top right; title, a three-line summary, then meta and a 40px round delete button and an Open pill. Hover lifts it 3px.
- **Choice tiles** (format options, Settings segmented choices): sheet inset, 20px radius, a 46px round icon well, title and description, a 20px radio ring top right. Chosen: amber-line border, amber-soft wash, amber icon well, and the ring filled as an amber dot.
- **Callouts:** sheet inset, 20px radius, hairline, 16px 18px. The approval panel is amber soft with an amber-line border at 24px radius.
- **Notices:** a sheet-coloured pill floating at the top centre of the map with an info or alert mask; drops in 12px.
- **Empty states:** one centred sheet (to 620px) with a route drawing, a heading, one line and one action. The empty library draws the amber route and offers to create; a search or filter that matches nothing keeps the same sheet and offers to clear itself. Processing with no jobs drops its list column and draws the route untravelled (dotted hairline, hollow stops).

### Inputs / Fields
- **Style:** sheet inset, a strong hairline, 14px radius, 46px tall, 11px 14px. Selects carry a stroke chevron, and where the browser supports a customizable select their open list is a sheet (18px radius, sheet shadow, 6px padding) of 40px rows with an amber-ink tick on the chosen one, rising 6px over 200ms; a long label is clipped before the chevron; textareas start at 96px; file inputs are a dashed 20px tile with a pin-coloured pill button.
- **Hover:** border to ink at 30%.
- **Focus:** border goes amber with a 4px amber-soft halo; elsewhere focus is a 2px amber outline at 3px offset.
- **Error:** bad border with a 3px bad-soft halo; form errors are a bad-soft panel with an alert mask. The link field is checked by the app, not the browser (`novalidate`): it takes the bad border and a 4px bad-soft halo, and the form error sits directly under it. A stopped job's error uses the same panel.
- **Link field:** the most used control. A 64px pill with a link icon, 1rem input text, and the primary Create button (48px) set inside its right end; it shares the field focus treatment.
- **Glass field:** a 52px frosted pill for controls on the map (library search and filter, the look editor's preview picker); focus adds the amber halo outside the glass shadow. The search field's clear control is the close mask in on-map muted, never the browser's own. Below 640px search and filter each take a full row.
- **Segmented tabs:** a sheet-inset pill track with 38px pill buttons; the pressed one fills amber with on-amber text.

### Navigation
- **Rail:** brand pin (52px white circle with the mark) and name; a frosted capsule of four nav items, each a 44px round pin over a 0.71875rem label. Rest: on-map muted label and a bare icon. Hover: glass-hover fills the pin. Active: the pin fills with the pin colour and lifts, the label goes on-map at 600, and `aria-current="page"` is set. Keyboard focus rings the pin (2px amber, 3px off), not the whole item.
- **Orbs:** 44px frosted rounds for theme and help; a sheet-coloured pill tooltip slides in from the right on hover or focus (hidden below 900px). Press scales to 0.95.
- **Settings rail:** a glass column of 44px rows with icons; active rows take the pin colour. Below 1100px it becomes a scrolling pill row.
- **Crumbs** (look editor): a small glass pill of links, the current item at 600.
- **Mobile:** the dock described in Layout.

### Job route (signature)
The job sheet shows a route pill and a route of five stops on a curved line (a 500 by 64 SVG stretched to the sheet). Done legs are solid ink at 55%; the live leg is a 3px amber dash (7 7) that flows at 1s per cycle; legs ahead are dotted hairlines. Stops alternate in height (44, 20, 44, 20, 32px). A stop ahead is a 14px hollow dot; done is a 22px pin with a check; live is a 26px amber dot ringed in sheet colour with a pulsing amber beacon; waiting for approval is a 24px sheet dot with an amber ring; arrived is a 34px amber pin. Names sit 70px down; live, waiting and arrived names go ink at 600. The pill counts the stops left in amber soft, becomes solid amber when arrived, bad when stopped and neutral when idle. Job rows in the list carry a 12px dot in the same grammar (live amber with a beacon, wait ringed, done good, error bad).

### Lobe (signature)
The hero sheet's tab draws the route a new source will take (Captions for a link, Transcript for a file, or Audio and Transcript for a recording; then Ideas; then Page, or Slide plan and Deck): a 2.5px amber curve with sheet-filled amber stops and a solid amber destination, the stop count in bold and a short note, and stop names beneath in micro type. It is an image with an accessible label naming the stops.

### Recent trail
At 1280px and wider, the last pages stand in a column of glass rows, each with a 58px terrain thumbnail at 16px radius, joined by a 2px dashed trail in on-map at 35%. Hover nudges a row 2px right.

### Look swatches
Each slide look is shown as a miniature slide: its surface, a title "Aa" in its display face, an accent bar, a statement panel on the right third, and five data bars, always in the look's light colours whatever the app theme. These belong to the slide looks, not the workspace palette. A chosen look, on the start sheet and in Settings, takes the chosen-tile treatment (amber border, amber-soft wash) and carries a 22px amber tick disc in the statement panel's empty lower corner, clear of the accent bar.

## Do's and Don'ts

### Do:
- **Do** keep the map (ground, two pools, contour mask) fixed behind every view in both themes.
- **Do** float work on sheets (28px radius, sheet shadow) and use glass only for controls that sit directly on the map.
- **Do** keep amber to routes, the live stop, pressed choices, counts and focus; read amber text in amber ink.
- **Do** make the primary action a pill in the pin colour: white at night, ink by day.
- **Do** draw progress as a route: curved legs, stops, a stops-left pill, an amber destination.
- **Do** give every source a generated terrain cover: one of the six survey tints and an offset into `terrain.svg`, both from a hash of its id.
- **Do** set all workspace text in Be Vietnam Pro and draw icons from the 1.6px stroke sprite.
- **Do** move with a 180 to 220ms exponential ease-out (`cubic-bezier(.16,1,.3,1)`): 180ms for colour, 200ms for scale and nudges, an 8px rise on a view or section, and nothing at all under reduced motion.
- **Do** respect the CSP: set per-item values (cover offsets, look swatch colours) through the CSSOM with `style.setProperty`, never inline style attributes; load masks and images only from `/static` or data URIs; serve fonts from `distill/web/fonts` with their provenance in its README.
- **Do** keep the look swatch markup and its `--look-*` custom properties (surface, display, ink, accent, feature, on-feature, data-1 to data-5): the browser tests read the swatch's background, its statement panel and its accent bar.
- **Do** keep theme.js's storage key and message types; saved pages embed a copy.

### Don't:
- **Don't** return to a grey sidebar beside a white grid of cards, or to the forest-green sidebar.
- **Don't** fill a primary button with amber outside a pin-coloured bar, or use amber as decoration.
- **Don't** put glass inside a sheet or stack glass on glass.
- **Don't** use hard offset shadows, or box-shadow on a lobed sheet.
- **Don't** add a second workspace typeface, uppercase letter-spaced labels or small text set above a heading.
- **Don't** use text glyphs or emoji as icons; add a symbol to the sprite.
- **Don't** load fonts, images or masks from another host, or write `style="..."` into markup.
- **Don't** restyle the saved pages and decks inside the reader frame from here; they are portable documents with their own styles.
