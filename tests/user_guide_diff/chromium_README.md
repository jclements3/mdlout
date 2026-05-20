# Chromium-headless variant of the User's Guide PS-vs-SVG diff

The default `tests/user_guide_diff.sh` pipeline rasterises Lout's SVG output
with `rsvg-convert`. `rsvg-convert` doesn't honour the `@font-face` Nimbus
base-35 fonts that `mdlout`'s HTML wrapper inlines, so the SVG-side render
uses whatever "Times" / "Helvetica" / "Courier" the system happens to expose
(usually Liberation / DejaVu) rather than the metric-matched URW++ Nimbus
that Ghostscript itself paints on the PostScript side.

This variant re-rasterises the SVG with **Chromium headless** instead, using
the exact `@font-face` Nimbus base-35 declarations `mdlout._build_font_face_css`
emits. That's the configuration a human user actually sees when they open
the HTML output of `mdlout` in a browser.

## Files

- `tests/chromium_diff.sh` -- runner (mirrors `user_guide_diff.sh` end-to-end).
- `tests/chromium_wrap_svg.py` -- per-page HTML wrapper + shared `@font-face`
  CSS generator (the spec list mirrors `mdlout._FONT_EMBED_SPECS`).
- `tests/user_guide_diff/chromium_manifest.txt` -- the per-page pixel-diff
  manifest produced by this run.
- `tests/user_guide_diff/chromium/worst-NN.png` -- side-by-side panels for
  the 10 pages where Chromium-vs-PS disagrees the most.

## Tooling actually used

- Chromium: this run picked up `/mnt/c/Program Files/Google/Chrome/Application/chrome.exe`
  (the WSL host's Chrome). The runner's auto-detect order tries native
  Chromium first (`/usr/bin/chromium`, `/snap/bin/chromium`,
  `/usr/bin/google-chrome`); the Windows fall-through is last.
- PS render is still `ps2pdf` + `pdftoppm -r 100` (unchanged from the rsvg
  variant). Each PS PNG is cropped from 827 x 1170 down to 826 x 1169 to
  match Chromium's screenshot extent (842 pt @ 100 dpi = 1169.44, rounds
  down).
- Diff: `compare -metric AE -fuzz 5%` (identical to the rsvg pipeline).

## Page subset

31 pages: the 10 worst-offenders from the existing rsvg run
(`019, 056, 063, 075, 086, 090, 094, 095, 248, 262`) plus 20 pages spread
evenly across the 327-page document (`001, 017, 033, 049, 065, 081, 097,
113, 129, 145, 161, 177, 193, 209, 225, 241, 257, 273, 289, 305, 321`).
Selection is automatic in `chromium_diff.sh` (re-runnable with a custom
subset by passing a comma-separated page list).

## Aggregate results (this run)

|             | Chromium + Nimbus @font-face | rsvg (baseline) |
|-------------|------------------------------|-----------------|
| mean diff   | **10.69 %**                  | 9.06 %          |
| median diff | 9.71 %                       | 7.91 %          |
| max diff    | 19.34 %                      | 19.48 %         |
| stdev       | 0.0399                       | 0.0373          |

Paired delta (chrome - rsvg): **mean +1.63 pp, median +1.84 pp**. Chromium
is worse than rsvg on 30 of the 31 sampled pages; the single page where
it improves (248) is the one where `rsvg` itself hits the cap because of a
graph-axes rendering glitch shared by both rasterisers.

OK / DIFF / BAD bucketing is unchanged:

| bucket          | Chromium | rsvg    |
|-----------------|----------|---------|
| OK (< 5 %)      | 2        | 2       |
| DIFF (5 - 20 %) | 29       | 29      |
| BAD (>= 20 %)   | 0        | 0       |

No page crosses into BAD under either renderer; no page that was DIFF
under rsvg drops into OK under Chromium. The whole-document story is
**worse**, not better.

## Why didn't the diff drop?

The `@font-face` Nimbus declarations *do* apply -- inspecting a hand-built
"with-fonts vs no-fonts" Chromium screenshot of page 017 confirms the
glyph outlines change shape when the embedded fonts are removed. The
remaining 1-2 pp gap is the font *rasteriser* rather than the font outlines:
Ghostscript (PS side) lays glyphs down on a 100-dpi grid with its own
PostScript-derived hinting, while Chromium (Skia + HarfBuzz) applies its
own grid fitting, subpixel positioning, and stem snapping. The resulting
glyphs are a half-pixel off in places, which the AE metric counts as a
"halo" around every letter.

`rsvg-convert` uses Cairo + FreeType, which happens to be closer to
Ghostscript's Type-1 hinting model. It cannot read `@font-face`, so it
falls back to whatever system Times / Helvetica / Courier fontconfig
serves -- on this Debian/Ubuntu system that's also URW++ Nimbus (via the
fonts-urw-base35 package), so the SVG and PS renders end up using the
same outlines anyway. That's the hidden reason rsvg "wins": its fallback
already lands on the right font *and* its rasteriser matches Ghostscript
better than Chromium's does.

## Worst-10 pages (this run)

| rank | page | chrome ratio | rsvg ratio | notes                                        |
|------|------|--------------|------------|----------------------------------------------|
| 1    | 248  | 0.1934       | 0.1948     | Chapter 10 graph axes; both renderers struggle |
| 2    | 086  | 0.1779       | 0.1462     | dense diag                                    |
| 3    | 090  | 0.1719       | 0.1404     | dense diag                                    |
| 4    | 063  | 0.1501       | 0.1213     |                                              |
| 5    | 095  | 0.1470       | 0.1182     |                                              |
| 6    | 056  | 0.1455       | 0.1220     |                                              |
| 7    | 094  | 0.1430       | 0.1183     |                                              |
| 8    | 262  | 0.1408       | 0.1345     |                                              |
| 9    | 075  | 0.1382       | 0.1165     |                                              |
| 10   | 081  | 0.1377       | 0.1133     |                                              |

See `chromium/worst-01.png` ... `chromium/worst-10.png` for side-by-side
PS / Chromium / DIFF panels at 50% scale.

## Reproducing

```bash
# 1. ensure the rsvg baseline artefacts exist (these provide the PS PNGs
#    and per-page split SVGs that the chromium pipeline reuses):
tests/user_guide_diff.sh

# 2. run the chromium variant on the default 31-page subset:
tests/chromium_diff.sh

# 3. or on an arbitrary subset:
tests/chromium_diff.sh 010,019,086,248
```

`chromium_diff.sh` shuttles its working files through `/mnt/c/temp/` when
it detects WSL (because Chromium on the Windows side struggles to load
`file://` URLs from the `\\wsl.localhost\` share). On a native Linux
system with `chromium-browser` or `google-chrome` on `$PATH` it stays
entirely under `/tmp/`.

## Is this good enough?

For the stated goal -- "measure how much the PS-vs-SVG pixel diff drops
when we render the SVG with the browser-style pipeline users actually
see" -- the answer is **measured, and no, it doesn't drop**. Browser-side
font rasterisation costs roughly +1.5 pp of pixel-diff compared with the
Cairo + system-Nimbus path. That's the number to point at any time
someone asks "should we ship a browser-validated HTML preview as the
canonical render?" -- it's slightly worse than the regression suite's
current rsvg baseline, not better.

Two follow-ups would be informative but are out of scope here:

1. Render the SVG in a Linux-native Chromium (or webkit-gtk via wkhtmltox
   / weasyprint) to see whether Skia-on-Windows vs Skia-on-Linux moves the
   needle. The current run uses the WSL-mounted Windows Chrome, which has
   DirectWrite font hinting; Linux Chrome uses FreeType + HarfBuzz, the
   same back-end as `rsvg-convert`, and may close the gap.
2. Switch the AE metric to a perceptual one (SSIM / Hash distance) so
   sub-pixel anti-aliasing differences don't dominate.
