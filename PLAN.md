# Walk-through plan

We are turning the flat Catalyst landing page into a 3D scroll walk-through.
Repo: https://github.com/pedram-kh/walk-through

## Big picture

- One pinned 3D scene. Scrolling moves the camera along a path through about
  16 stops. Each stop is one section of the flat page rebuilt as a 3D scene.
  The camera rests at each stop, then travels to the next.
- The existing hero (tile wall, galaxy dust, particle current: `hero.js`,
  `build_layout.py`) is stop 1. It is approved as a scene.
- We build one stop at a time. Only after a stop is approved do we start the
  next one.
- Reference for the sections: `Catalyst AI Landing (standalone).html` (not
  final). Screenshots per stop come with each stop's brief.

## How each stop is built

1. You provide reference images. I ask the questions under "Content and
   buttons" and wait for your answers.
2. Blender graybox: a Python script places simple shapes and extends the camera
   path from the previous stop to this one. Render a preview and wait for
   approval of composition and travel.
3. Blender detail: real geometry and materials, still from a script.
4. Export this stop as its own files, then wire it into the browser.
5. Add the behaviour, text and buttons exactly as answered.
6. Check it, record the numbers here, commit, and report. Then wait.

Nothing is built, changed or pushed for a new stop without your confirmation.

## Content and buttons: ask, do not assume

Before building any stop, ask these and wait for the answers:

1. Text: what text appears at this stop, and for each piece, is it HTML over
   the scene or part of the 3D model?
2. Buttons: which buttons does this stop have, what does each one do when
   clicked, and is each one a 3D object or an HTML button?
3. Button behaviour: how should each button look at rest, on hover and on
   click, and how should it act as the camera approaches and leaves (grow with
   distance, fade in on arrival, stay fixed on screen, or other)?
4. Scene behaviour: what moves when idle, what reacts to the cursor, what
   happens on click or drag, and what happens as the camera arrives and leaves.
5. Media: which images or videos belong to this stop, and where they sit.

Do not choose any of these myself. If an answer leaves something open, ask
again. If a choice will hurt performance, keyboard access or the fallback page,
say so in one line and let you decide. Record the answers in that stop's
`stop.json` before building.

## Transition design (decided 2026-10-03)

Every move from stop N to stop N+1 plays these phases, driven by scroll.
Scrolling back plays them in reverse.

| Phase | What the visitor sees |
|---|---|
| A. Rest | Stop N in colour and live (particles, videos, cursor), its section's HTML fully on screen. |
| B. Freeze | At the very first scroll movement away from rest: particles and videos stop, the 3D fades to black and white. |
| C. Curtain up | The section's HTML scrolls up like a normal page, uncovering the frozen 3D. |
| D. Empty | No section HTML on screen; only the frozen black-and-white 3D. |
| E. Curl | The camera rides a half circle that swings toward the stop's objects (closest halfway round) while tilting evenly; radius and tilt angle are set per stop (`enter.radius`, `enter.tilt_degrees`, default 90). |
| F. Travel | The camera moves to stop N+1. |
| G. Arrive | Stop N+1 arrives frozen and black and white. Its HTML scrolls up into view. |
| H. Live | Once the whole section's HTML is on screen, stop N+1 turns to colour (if it has a colour version) and comes alive. |

- The tilt in phase E is per transition: down, up, left or right, and its angle
  (`tilt_degrees`). Everything else in the move is the same every time.
- The particle current runs through the whole route (decided 2026-10-03): each
  stop's current wraps its objects and leaves the frame toward the camera's dive;
  a journey current (`currents/tNN.bin`, built by `tools/build_route.py`) picks it
  up and runs ahead of the camera to the next stop. Like everything else it
  freezes when scrolling starts and flows only while a neighbouring stop is live.
  Each new stop's brief includes where the current enters and leaves it.
- The nav bar is fixed at the top at all times; it is not part of any curtain.
- The camera follows the scroll with a short glide (`FOLLOW_SECONDS` in
  `runtime/runtime.js`, 0.12 s), so wheel steps don't jump; the page itself
  scrolls natively. Each journey's spacer is 2 screens (`SPACER_SCREENS` in
  `tools/build_route.py`), with 240 camera samples per journey (decided 2026-10-04).
- Implementation: the flat page stays real HTML in normal document flow, one
  block per section. Between sections sits an empty spacer whose height is the
  camera journey. While a spacer fills the screen (phase D) the scroll position
  drives the curl and travel (E, F). The curtain is therefore ordinary page
  scrolling: keyboard, scrollbar and screen readers keep working, and the
  visible page is the real content (no hidden text for search engines).
- Freeze and black and white are one switch per stop: time stops, videos
  pause, and a grey uniform on the stop's materials goes 0 to 1 over ~0.5 s.

## Stops (tentative, from the reference HTML; confirmed one by one)

| Stop | Section | Notes |
|---|---|---|
| 01 | Hero | Approved scene (tile wall, dust, current). |
| 02 | Creative for (client logos) | Its own stop, in 3D. Logo grid: Lovable, fyxer, MAGIC AI, Mozart, cleo, VIKTOR, Jack & Jill, plus Perplexity, Granola and Canva in the two empty top-left slots and the empty bottom-right slot. |
| 03 | 02 The problem | |
| 04 | 13 Creative cycle | Moved up on 2026-10-04: landing sections 03-12 are skipped for now and may be added later (the rows below keep the original plan for reference). |
| 05 | 04 Creative translation | |
| 06 | 05 Input: one product | |
| 07 | Different audiences / use cases / messages | Unnumbered in the reference; may merge with 06. |
| 08 | 07 Output: different formats | |
| 09 | 08 Test | |
| 10 | 09 Learn | |
| 11 | 10 Iterate | |
| 12 | 11 Scale | |
| 13 | 12 Real performance | |
| 14 | 13 Creative cycle | |
| 15 | 14 Full service | |
| 16 | 15 Pricing | Footer follows in plain HTML. |

## Architecture

- Each stop lives in `stops/NN-name/` with its build script, `.blend`, GLB, data
  files, media, a still poster and a `stop.json` contract.
- `route.json` at the root lists the stops in order, the camera path, the
  camera orientation along it, and each stop's scroll anchors and rest view.
- One runtime owns the renderer, camera, scroll progress, the route, the
  pointer and the nav. Each stop is a module with `load()`, `enter()`,
  `update(progress)`, `leave()`, `dispose()`, plus `setFrozen(bool)` and
  `setGrey(0..1)` for the transition. No stop reaches into another stop.
- Blender owns shapes, positions and the camera path. The browser owns all
  motion, interaction and video. Blender materials are for the preview render;
  the browser rebuilds each material in three.js (as `hero.js` does now).

### Folder layout (built 2026-10-03)

```
index.html              flat page: fixed nav, every section in order, spacers between them
style.css               page, section and route styles (html.route = 3D mode)
app.js                  chooses 3D route or flat page (touch, reduced motion, failure)
route.json              built by tools/build_route.py from the stops' stop.json files
assets/                 page-level files (logo)
runtime/
  runtime.js            renderer, camera fitting, pointer, frame loop, freeze/grey, journey currents, fps guard, diagnostics
  flow.js               particle current shader and builder, shared by stops and journey currents
  route.js              scroll -> camera pose and phase, measured from the section and spacer elements
  loader.js             loads N..N+2 (and N-1, N-2) one at a time, disposes further back, poster planes
  dots.js               progress dots on the left; click flies through by animating the scroll
  materials.js          shared black-and-white helper for stop materials
  bench.js              ?bench: drives the route and prints fps per stop and phase
stops/
  01-hero/              build.py, stop.js, stop.json, stop.glb, dust.bin, flow.bin, stop.blend, poster.jpg, media/
  02-clients/           "Creative for" logo grid: build.py, stop.js, stop.json, stop.glb, dust.bin, flow.bin, stop.blend, poster.jpg
tools/
  build_route.py        Blender script: chains the stops (half circle, tilt, travel) -> route.json, journey
                        currents -> currents/tNN.bin, camera clearance check
  flow_common.py        shared current helpers (paths, frames, particles) for build scripts
currents/               journey currents between stops, built by tools/build_route.py
vendor/three/           unchanged
```

Stop module interface (`stops/NN-name/stop.js`): `load(ctx)` returns
`{ group, setFrozen(bool), setGrey(0..1), setVisible(bool), resize(size), update(dt), dispose() }`.
`ctx` gives the stop its folder, the shared camera, the caption overlay, the pointer
and `invalidate()`. Shared Blender helpers live in `tools/` (`flow_common.py` for currents).

### route.json format (built 2026-10-03)

World units are scene units, Y up (three.js). Each stop sits at its own origin
in the world, so stops never overlap.

```json
{
  "version": 1,
  "stops": [
    {
      "id": "01-hero",
      "dir": "stops/01-hero/",
      "origin": [0, 0, 0],
      "rotation": [0, 0, 0, 1],
      "rest": { "position": [0, -0.2, 11], "quaternion": [0, 0, 0, 1], "fov": 65.47, "designAspect": 1.8469 },
      "section": "#s01",
      "poster": "stops/01-hero/poster.jpg",
      "sizeBytes": 0
    }
  ],
  "segments": [
    {
      "from": "01-hero",
      "to": "02-clients",
      "tilt": "down",
      "spacer": "#t01",
      "spacerScreens": 1.5,
      "samples": 120,
      "position": [[0, -0.2, 11], "..."],
      "quaternion": [[0, 0, 0, 1], "..."]
    }
  ]
}
```

- `section` and `spacer` are element ids in `index.html`. The runtime measures
  them, so scroll ranges adapt to any screen size: rest is "section fully on
  screen", travel is "spacer on screen".
- The camera path is stored as evenly spaced samples of position and
  orientation (quaternions, so 90-degree tilts in any direction and the curl
  need no special cases). Blender writes them; the browser only interpolates.
- `tilt` records the direction for reference; the samples already contain it.

### Changes to the current hero to make it stop 1

1. Split `hero.js`: renderer, camera fitting, resize, pixel-ratio guard, fps
   diagnostics, context loss and the pointer go to the runtime; tiles, dust,
   current, videos and tile captions become `stops/01-hero/stop.js` with the
   module interface.
2. Camera: the rest view comes from `route.json` instead of `hero.json`. The
   design-frame fitting (keep the designed frame on any aspect) moves to the
   runtime and applies at every rest view.
3. Freeze and grey: add a grey uniform to the photo, video, galaxy, dust and
   current materials; `setFrozen` stops the clock and pauses videos (today this
   is `setActive`).
4. HTML: the hero copy becomes section `#s01` of the flat page in normal flow;
   the nav moves out of the hero to a fixed page-level header; the Pause button
   becomes global; the tile captions stay with the stop.
5. Files move into `stops/01-hero/`; `build_layout.py` becomes `build.py`,
   writes there, and uses shared helpers from `tools/`. `media.json` paths update.
6. Budgets: stop 1 keeps its three videos and its size (agreed exceptions).
7. Fallback: `app.js` keeps its checks; the fallback becomes the flat page with
   each stop's poster.

## Jump navigation (decided 2026-10-03)

- Progress dots, vertical, on the left side of the screen, one per stop.
- Owned by the runtime (page level, like the nav bar).
- Still open: what a click does (fly quickly through the stops in between, or
  cut to the stop with a short fade); whether dots show section names on hover;
  dot placement against the left-hand copy and the "Strategy / Production" list.

## Rule 1: performance (one shared budget)

- Test device: this Mac, Intel Iris Plus Graphics, 1920 x 1080. It must hold
  30 fps or better through the whole route.
- Only the stop at the camera animates, simulates and plays video. The previous
  and next stops are visible but frozen. All others are hidden and cost nothing.
- Per stop: at most 60,000 triangles, 40 draw calls and one playing video.
  Pixel ratio capped at 1.5. Tell you before exceeding a budget.
- Agreed exception: stop 01 plays three videos (Motion, centre, UGC).
- After every stop, measure fps resting at it and travelling in and out, and
  log it below with the date. If the route drops below 30 fps, fix that before
  starting a new stop.
- Measuring: the preview browser I use throttles itself when hidden, so fps is
  measured with `?bench` in your Chrome (it scrolls the route and prints fps per
  stop and phase), and the numbers are pasted into the log below.

## Rule 2: loading (each stop is its own download)

- Stop 1 loads first and shows as soon as it is ready. Nothing else blocks it.
- While the visitor is at stop N, load stops N+1 and N+2 in the background.
  Dispose stops more than two behind the camera and reload them if the visitor
  scrolls back.
- If a stop is not ready when the camera arrives, show its poster on a plane
  and swap in the live version when loaded. Never freeze the scroll.
- Keep each stop under 2 MB excluding video. Log each stop's size below.
- Agreed exception: stop 01 stays at its current size (~6.1 MB excluding video).

## Fallback

- The flat page stays in the HTML as the real content for search engines,
  keyboards and screen readers (and it is the visible content in 3D mode too).
- Touch devices, reduced motion and any graphics failure get the flat page with
  the stop posters instead of the 3D route.

## Machine

- Blender 4.5.14 LTS on an Intel Mac, run in the background:
  `/Applications/Blender.app/Contents/MacOS/Blender --background --python <script>`
- Render with Cycles on CPU, low samples. Scripts must be deterministic.
- Serve with: `python3 -m http.server 4175`

## Review notes and open items

- Stop 1 fps has not been measured on the Iris Plus since the particle current
  was added (27,000 points). First `?bench` run will tell.
- Phase A to B is "the very first scroll movement". If the visitor stops between
  rest positions, the scene stays frozen until they return to a rest position.
  Optional: snap to the nearest rest position when scrolling stops (not decided).
- Stop 02 needs logo artwork for all ten brands (SVG preferred) and the
  reference page's grid and typography; to be asked when stop 02 starts.

## Log

| Date | Stop | Event | Rest fps | Travel fps | Size (excl. video) |
|---|---|---|---|---|---|
| 2026-10-03 | 01 | Hero approved as a scene; first commit pushed | not measured | n/a | 6.1 MB |
| 2026-10-03 | 01 | Exceptions agreed: three videos, size above 2 MB | | | |
| 2026-10-03 | 01 to 02 | Route skeleton: hero as stop 01, placeholder stop 02, curtain, freeze and grey, curl and 90-degree tilt down, travel, dots, flat fallback | not measured (run ?bench) | not measured | 01: 6.1 MB, 02: 0.1 MB |
| 2026-10-03 | 01 to 02 | Transition move: half circle (radius 8) swinging toward the objects while tilting 90 degrees, then travel 14; clearance check in build_route.py (closest pass 4.4 units) | not measured | not measured | |
| 2026-10-03 | 01 to 02 | Tilt 60 degrees, travel 8; current continues through the journey (stop 01 tail rerouted, currents/t01.bin, 10,441 particles); ~56k points on screen during the journey | not measured (run ?bench) | not measured | journey current 0.45 MB |
| 2026-10-03 | 01 to 02 | Frame rate judged OK by eye on the test Mac; no ?bench numbers yet | OK (by eye) | OK (by eye) | |
| 2026-10-04 | 02 | Brief recorded in stop.json; graybox approved (5 x 2 grid at varied depths, current threads the middle line and leaves left, journey current hands over to it) | not measured | not measured | 0.7 MB (graybox) |
| 2026-10-04 | 02 | Detail + behaviour built: wordmarks in their real fonts, grid merged to 3 draw calls (5 for the stop, 15.5k triangles), hover like catalyst-growth.com (lift, corner glow, rotating gradient border, wordmark brighten/dim), dust and current part around the cursor; flat page shows the brands as a list. Awaiting approval | not measured (preview pane) | not measured | 1.59 MB (+ journey current 0.49 MB) |
| 2026-10-04 | 02 | Dust removed at your request: the current is the only particles at stop 02 | 60 (preview, at rest) | not measured | 1.51 MB |
| 2026-10-04 | 01 to 02 | Smoother, shorter scrolling: camera glides after the scroll (0.12 s), journeys 3 -> 2 screens (page 5 -> 4 screens so far), camera path 120 -> 240 samples | not measured | not measured | |
| 2026-10-04 | 02 | Stop 02 approved (hover matched to the live site, hovered cell drawn in front, lift 0.4) | 60 (preview) | not measured | 1.51 MB |
| 2026-10-04 | 03 | Brief recorded in stop.json; graybox approved: three rows of 5 upright cards turned 25 degrees in a checkerboard zigzag (toward / away from the screen), all text in HTML around them and the whole section in one viewport; current enters from the right, goes around the cards in two strands and leaves through the top-right; turn left 60 degrees from stop 02. Journey currents now stay out of the next stop's arrival view when its current starts off screen | not measured | not measured | 0.85 MB (graybox, + journey current 0.52 MB) |
| 2026-10-04 | 03 | Detail + behaviour built: card faces from the catalyst-growth.com photos (stop 01 set) with the landing's hairline border and label chip in one texture (cards.jpg, atlas.py); 6 cards per row in the drift loop (5 on screen), drifting like the landing (rows 1 and 3 right, row 2 left), fading per pixel at the row ends and wrapping off screen so the checkerboard holds; hero-style tilt and lift near the cursor; the landing's violet-to-blue motion trail behind each row; colour when live. 5 draw calls for the stop. Awaiting approval | not measured (preview pane) | not measured | 1.3 MB (+ journey current 0.52 MB) |
| 2026-10-04 | 03 | Stop 03 approved ('02 — The problem' label removed at your request) | not measured | not measured | 1.3 MB |
| 2026-10-04 | 04 | Brief recorded in stop.json (landing section 13, Creative cycle, as stop 04; sections 03-12 skipped for now). Graybox built: ring on the left with stage spheres, signal, trail and the extruded Catalyst mark; title, rows and stage labels in HTML; current from below, around the ring, out to the left; turn up 60 degrees from stop 03 (closest pass 4.7 units). Graybox approved | not measured | not measured | |
| 2026-10-04 | 04 | Detail + behaviour built: ring, trail (the landing's conic violet-blue-teal), stage spheres with rim and centre colours and glows, signal, halo and core glow drawn in the browser from stop.json; the extruded mark from stop.glb (36 KB). Signal runs at the landing's timing (1.8 s per stage, eased settle); the reached stage lights in its colour, with its row and label; hover, focus or click on a row moves the signal there and holds it. Mark tilts and lifts a little near the cursor. Runtime: stops now get their section element in ctx. 11 draw calls for the stop. Awaiting approval | not measured | not measured | 0.6 MB (+ journey current 0.5 MB) |
| 2026-10-04 | 04 | Changes at your request: the ring turns on its vertical axis (one turn in 30 s); the stage labels are 3D (canvas text in the page's mono font, following their spheres and facing the camera); the list's lines and the active underline are 3D, measured from the HTML rows, so only the text leaves with the curtain. 13 draw calls. Awaiting approval | not measured | not measured | 0.6 MB |
| 2026-10-05 | 04 | Stop 04 approved | not measured | not measured | 0.6 MB |
| 2026-10-05 | 01 | Dust removed at your request: stop.js no longer loads or draws dust.bin, so the current is the only particles at the hero (the build and the poster still include the dust; rebuilding stop 01 would reshuffle its approved current). Approved | not measured | not measured | 0.59 MB less to download (dust.bin no longer fetched) |
| 2026-10-05 | 01 | Removed at your request: the 'Strategy / Production / Performance / Scale' list and the thin vertical background lines (HTML and CSS). Approved | not measured | not measured | |
| 2026-10-05 | all | Currents 40% less dense at your request: runtime/flow.js draws a fixed, even 60% of every current's particles (CURRENT_DENSITY 0.6), stops and journeys alike; paths unchanged, no rebuilds. Points on screen at the hero 45,013 -> 27,045. Approved | not measured | not measured | |
| 2026-10-05 | 01 | Mono tiles restyled at your request, after catalyst-growth.com's photos: soft muted black and white (cool blue-grey lights, deep blacks) under a halftone screen, teal / violet fringes where shadow meets light, faint coloured grain in the blacks. Halftone anti-aliased and faded where it would cause moire; grain in screen pixels. The 8 colour tiles are unchanged; the poster still shows the old look. Approved | not measured | not measured | |
| 2026-10-05 | all | Hold zones at your request: each section is wrapped in a hold element half a screen taller than the screen (section sticky inside), so every stop stays live and in colour for an extra half screen of scrolling; the stop's dot becomes a pill that fills violet -> teal through it, then the curtain and journey start. Colour starts fading in over the last 20% of a journey into a stop (direction-aware). Inside a hold zone, wheel / trackpad scrolling is braked (x0.55, max 8% of a screen per event; touch left native). Scroll snapping removed (it would pull the page back out of a hold zone). Dots fly to the start of a hold zone. Page 12 screens for 4 stops (was 10). Then: the pill is black, filling white (not the gradient), and no single wheel step can carry the page into a zone past its edge, so every arrival from above starts with an empty pill. Approved | not measured | not measured | |
| 2026-10-05 | all | Pause motion button removed at your request (visitors with reduced motion set still get the flat page). Approved | not measured | not measured | |
