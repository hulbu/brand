# Building Hulbu’s kit

Run `python3 source/build.py` from the repo root (or call it by absolute path). Install `source/requirements.txt` first. The build works offline and generates assets, tokens, documentation, licensing text, the review page and contact sheets. No external fonts or image services are used.

- `brand.json`: editable colour tokens, fixed geometry and requested profile sizes. Coral lives only at `palette.primary.hex`.
- `build.py`: exact circular paths, rasterization, deterministic ICO packaging, covers, profiles, swatches and output inventory.
- `templates/`: source text for README, license, platform evidence and the preview page. Colour substitutions use the source tokens.
- `validate.py`: required inventory, SVG restrictions, sizes, colour and geometry checks, transparency, safe areas, ICO entries, internal links and contact-sheet coverage.
- `check-browser.mjs`: optional Chromium comparison against the original mask-based SVGs, automatic favicon colour-scheme test and review-page checks.
- `asset-manifest.json`: generated inventory including platform crop guides.
- `favicon-from-studio/`: preserved original studio material. Never modified by the build.

## Exact paths

For two circles separated by distance d, radius R and cutter radius S = R + gap, their intersection relative to the rear circle is:

```
a = (R² - S² + d²) / (2d)
h = sqrt(R² - a²)
```

The rear shape follows the left-side outside arc (long for gaps 22/32, short for gap 44) between `(cx+a, cy-h)` and `(cx+a, cy+h)`, then the cutter’s short inside arc back to the start. The front is a complete circle made from two arcs. Arc endpoints are serialized to nine decimal places; circles remain circular arcs, never polygon approximations.
The back circle needs only the middle cutter: within its vertical extent, the equal-radius front cutter is entirely to the right of the middle cutter’s left boundary, so it removes no additional visible area.

Logo viewBox: `285 390 510 300`. Favicon viewBox: `280 280 520 520`. Integer favicon framing changes the studio reference’s 520.2-unit canvas by just 0.0385% without changing any mark geometry. Favicon rasterization happens directly at each target pixel size. Large PNG heights are rounded from 300/510 of the requested width.
Profiles and the maskable icon use a 68%-wide mark. Even their bounding-box corners lie within radius 39.5% of the canvas, inside the 40% maskable safe circle and the 50% social circular crop.

## Checks

```sh
python3 source/validate.py
npm ci
npx playwright install chromium
npm run check:browser
```

The browser check renders the original reference and the path replacement in identical viewBoxes at 1040 × 1040, compares pixels, checks dark-mode colours, loads every preview image, verifies interactive controls at desktop and mobile widths, and writes review evidence to `.cache/browser/`.
It is separate from the offline build so building the kit does not require Node or a browser.

Open `preview.html` locally to browse or download every public visual. Toggle circular profile crops and cover guides; the PNG downloads remain unaffected. `review/contact-*.png` shows every shipped PNG and the preserved studio PNGs, labelled by path. The native favicon strip in the preview uses exact CSS pixel sizes. Review at 100% zoom.

The generator does not delete unrelated files. If retiring an export, remove its obsolete generated file explicitly after reviewing the inventory. Never put private source material in this public repo.
