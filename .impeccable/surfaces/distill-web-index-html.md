---
version: 1
slug: "distill-web-index-html"
primary_target: "distill/web/index.html"
related_targets: ["distill/web/app.css","distill/web/app.js"]
---

# Distill workspace

Scope: the whole workspace in `distill/web` (Create, Library, Processing, reader shell, Settings, look editor, share dialog). Saved pages and decks inside the reader frame keep their own styles.

Visitor mode: Operate. The owner makes a page or deck from a source, follows the job, then explores or presents from the library. Frequent, short visits; the link field is the most used control.

Constraints: strict CSP (no inline style attributes, no external fonts or images), ids and accessible names the Playwright tests use, theme.js message contract, Vietnamese and English copy.

## Direction contract

THESIS: The workspace is an atlas of what you are learning. Work floats over a dark topographic map, and every job is a route you watch advance stop by stop. It refuses the SaaS default of a grey sidebar beside a white grid of cards, and the old forest-green sidebar.

OWN-WORLD: Night ground #0e1416 with faint generated contour lines and two atmosphere pools (teal high right, amber low left); day ground is a pale survey map with ink contours. Floating sheets in graphite (night) or white (day), 28px radius, a shadow that follows the shape, and one tab-shaped lobe on hero sheets. Frosted round 44px controls only where they float over the map. White pins with ink icons; amber #f5a524 is the single signal colour for routes, the live stop, selected chips and count badges. Primary action is a white pill at night, an ink pill by day. Be Vietnam Pro, one family, 400 to 700. Authored 1.6px stroke icons.

STORY: The visitor sees where they are from the pinned rail, knows what they can make, and pastes a link. In Processing they watch the route advance and approve anything paid. In the Library every source has its own terrain cover, and opening one goes straight to the page or deck.

FIRST VIEWPORT: Create at 1440x900. A glass rail floats 16px off the left edge: brand pin, four labelled pins (Create lit white), theme and help at the foot. On the map, top left, the heading "What do you want to make?" with a live library count beneath. The hero sheet, about 760px, holds the two format choices, the slide-look row for slides, the source tabs, a 64px pill link field with the primary Create button inside its right end, the saved defaults as label and value chips, and the options disclosure. Its lobe, bottom right, draws the amber route Link, Ideas, Page. On wide screens a Recent stack of terrain covers sits to the right.

FORM: Navigation-map app UI, pinned by the user's Dribbble reference (Nixtio, "Bike Rental & Navigation App UI Design"), position 1 of 1. No roll ran: the user pinned the direction, which the skill says beats the roll, so there is no seed reference (seed: none, roll skipped for a pinned direction). Signature interaction: the job route, stops on a curved line whose live leg flows in amber dashes and whose pill counts the stops left; the destination pin fills amber when the page is ready. Motion grammar: 180 to 220ms exponential ease-out on state change, one 8px rise on a view's sheet, no load choreography, all of it off under reduced motion.

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance

## Unresolved

- Whether saved pages and decks inside the reader should later adopt the same world (they are portable documents with their own tests).
