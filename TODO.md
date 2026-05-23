# mdlout TODO

Working-engineer task list for the SVG/HTML output path of mdlout,
driven by the SVG back-end (`z53.c`) in the C Lout fork
(`jclements3/lout`, branch `svg-backend`).

For the historical record (what shipped in each release), see
[CHANGELOG.md](CHANGELOG.md). For forward-looking v0.3+ planning,
see [ROADMAP.md](ROADMAP.md).

## Status as of 2026-05-23 (v0.2.8 line)

The v0.2 line is the "HTML by default" release and is feature-locked.
Everything that was open against v0.2 in the previous TODO snapshots
has now landed:

- HTML/SVG output via the new `z53.c` back-end (v0.2.0).
- `@Math` / `@DMath` / `@ABC` / `@Mermaid` / `@SVG` / `@SVGFile`
  passthrough macros, with KaTeX + abcjsharp + mermaid.js inlined
  client-side (v0.2.0-v0.2.2).
- WCAG 2.1 AA accessibility scaffold in the HTML wrapper
  (landmarks, ARIA, skip-link, alt-text manifest, image-alt
  sidecar) (v0.2.0).
- `mdlout --watch` and `mdlout --serve [PORT]` (stdlib-only,
  SSE live-reload; port-probe over 20 ports as of v0.2.7).
- 327-page per-page User's Guide PS-vs-SVG diff harness
  (`tests/user_guide_diff/`) at the 150 DPI release-gate
  baseline (v0.2.6), with a 200 DPI sensitivity row confirming
  the AA / hinting structural floor (v0.2.7). Mean SSIM
  **0.9441** at 150 DPI (was 0.9283 at 100 DPI on the same
  corpus).
- Type 1 `.pfb` outline parser (v0.2.2), CFF/OTF outline parser
  (v0.2.2), TrueType `.ttf` outline parser (v0.2.3) -- all
  through the shared `z53_glyph.c` `charpath` path.
- AFM kerning consumed in SVG text emission (v0.2.2),
  precomputed per-font 256x256 kern table (v0.2.5).
- fi / fl / ffi / ffl ligature substitution on the
  Adobe-Type serif allowlist (v0.2.5).
- GSUB `smcp` / `onum` parser (v0.2.5) and consumer-side
  glyph emission via `<path d="...">` outlines with an LRU
  `(font, gid, size)` cache (v0.2.6); end-to-end working
  via frontmatter `font-features: smcp,onum`.
- Font subsetting default-ON; `--no-subset-fonts` opts out
  (v0.2.5; ~56% HTML size reduction across the example
  corpus).
- Dark mode via a proper `currentColor` cascade -- `z53.c`
  folds default-black ink to `fill="currentColor"`, the dark
  theme retints by setting `color:` on the page wrapper
  instead of inverting each page wholesale (v0.2.3 /
  v0.2.6).
- User's Guide SVG build under 30 s (v0.2.7, now **22.6 s**
  real / 19.8 s user on the reference host; the original
  v0.4 < 30 s stretch target is cleared by ~7 s).
- 90-snippet single-feature regression corpus (was 53 at
  v0.2.0, 85 at v0.2.8; 90+ now under the post-v0.2 tightened
  thresholds: 5% AE for text, 2% AE / SSIM 0.95 for
  graphics-heavy) -- 100% Pass-Excellent.
- Examples corpus at 34+ files under `examples/` (was 8 at
  v0.2.0).
- Cookbook at **50** recipes (was 32 mid-v0.2; final 50th
  landed at recipe count 50 in `docs/cookbook.md`).
- All four Lout-source docs (`design`, `expert`, `slides`,
  `user`) rendered end-to-end through `z53.c` with a
  landing page (`tests/lout_doc_renders/`); zero residual
  SVG `@Case` warnings as of v0.2.3.

Frozen / explicitly preserved:

- PostScript back-end (`z49.c`) -- bit-identical PDF output
  to the pre-z53.c era.
- PDF pipeline orchestration in `mdlout.py` (`--format=pdf`)
  -- bit-identical to v0.2.0.

## 1. Open items against v0.2

These are the residuals that the v0.2 line is willing to ship
with. They are tracked here rather than in ROADMAP.md because
they belong to the working-engineer task list, not the next
release theme.

  - [ ] **`z53.c` path save / restore on `gsave` / `grestore`**
        (issue #208). The embedded PS interpreter saves and
        restores graphic state (colour, line width, transform)
        across `gsave` / `grestore` pairs, but the current
        path is not saved. External `@Graphic` payloads that
        build a path, `gsave` to stroke it once, `grestore`,
        then continue building from the saved cursor lose the
        cursor. Folds into the broader "more aggressive
        `@Graphic` raw-PS to SVG translation" item below.
  - [ ] **More aggressive `@Graphic` raw-PS to SVG translation.**
        The embedded PS interpreter in `z53.c` handles the
        prologue idioms emitted by Lout's own `diagf.lpg` /
        `graphf.lpg` / `tabf.lpg` well, but external
        `@Graphic` payloads (user-supplied raw PostScript
        snippets) still occasionally fall through to per-op
        fallback (a rate-limited XML comment in the SVG).
        Target bar: PostScript snippets that ship inside the
        Adobe AppendixA-style cookbooks.

## 2. Open items deferred to v0.3+

Tracked here for visibility; primary ownership lives in
ROADMAP.md "Mid-term (v0.4 target)".

  - [ ] **Cross-token kerning** (p032; investigation under
        issue #188). Kerning is precomputed per-font and
        applied within a single Lout word (`<text>` element);
        kern pairs that span two adjacent words on the same
        line are not applied. Deferred; documented.
  - [ ] **Shared rasteriser for true pixel parity.** The
        current ~5% antialiasing floor on the User's Guide
        diff is rsvg vs Ghostscript painting the same glyph
        outlines with different AA / hinting choices
        (confirmed by `docs/chapter3_pagination_drift_investigation.md`).
        Out of scope for v0.2 because it depends on
        Ghostscript-vs-rsvg or a Chrome `--print-to-pdf`
        baseline; see ROADMAP.md.
  - [ ] **PyPI publish.** `pyproject.toml` builds a clean
        sdist + wheel; the `python3 -m twine upload dist/*`
        step is manual and pending the user's PyPI token in
        `~/.pypirc`.
  - [ ] **CI workflows OAuth refresh.** GitHub Actions
        workflows for the lout submodule cross-builds and
        the headless-Chrome regression runner are pinned
        against an OAuth token that needs the user to refresh
        in the repository settings. Manual; pending user.

## 3. Living documentation

  - [ ] Keep `lout/SVG_PORTING.md` current as `z53.c` grows.
        (Living doc; updated each release cycle.)

## 4. Orthogonal future work (not for this cycle)

Explicitly out of scope. Listed only so they are not forgotten.

  - [ ] C Lout UTF-8 input layer (z02.c / z03.c / FULL_CHAR
        widening).
  - [ ] C Lout PDF colour completion in z48.c / z50.c (only
        relevant if the PDF path is ever unfrozen; see the
        "unfreeze z49.c" decision in ROADMAP.md's v1.0
        section).
  - [ ] Font role abstraction in mdlout frontmatter.
  - [ ] CommonMark indented code blocks (currently
        unsupported; fenced blocks are the recommended path).

---

Last refreshed: 2026-05-23 (post-v0.2.8). See
[CHANGELOG.md](CHANGELOG.md) for the release history this list
projects from, and [ROADMAP.md](ROADMAP.md) for the v0.3+
forward plan.
