# Performance

Consolidated history of the SVG back-end (`z53.c`) performance work and the
measurement infrastructure that underpins it. The PostScript path (`z49.c`)
is frozen; numbers below all refer to the SVG/HTML build (`lout -G`).

The authoritative living document is [`lout/SVG_PERFORMANCE.md`][svgperf] in
the submodule (round-by-round audit and gprof tables). This page is the
project-level summary that ties it to the test harness
([`tests/bench.html`][benchhtml] / [`tests/bench.jsonl`][benchjsonl]), the
DPI-sensitivity work in
[`tests/user_guide_diff/README.md`][ugdiff], and the gprof snapshot under
[`tests/profile/README.md`][profile].

## 1. Headline

- **User's Guide (UG) SVG build, single pass, warm cache, WSL2 host:**
  pre-perf-work wall ~7 min (~420 s under instrumented `-pg` plus a 7-pass
  cross-reference loop) → current best-of-three **~22.6 s** wall (`lout -r3
  -G all`). That is roughly a **95% reduction** measured cumulatively across
  the five perf rounds documented below; the largest single jump is the
  round-3 `svg_ps_exec_op` hash dispatch (commit `2a33e3d`, ~77 s → ~32 s).
- **UG visual fidelity (PS vs SVG, raster diff):** mean SSIM started in the
  high 0.8s on the 100-dpi 327-page corpus (v0.2.0 reported 0.9230 over the
  same set, individual chapter clusters dipped into 0.85–0.88) and is now
  **0.9510 at 200 dpi** on the same pages (0.9441 at 150 dpi, 0.9283 at 100
  dpi). At 200 dpi 181/327 pages clear the 0.95 "visually
  indistinguishable" band and 0 pages remain below 0.85.

## 2. Round history

Each row layers on top of the previous one. Wall/user times are
single-pass UG builds (`cd lout/doc/user && rm -f *.li && time ../../lout
-I ../../include -I . -G all > /tmp/user.svg`), best-of-three on this
WSL2 host. Pre-round-1 baseline before any perf work landed was ~77 s
wall / ~40–49 s user on the same command. Source for each row is the
matching entry in [`lout/SVG_PERFORMANCE.md`][svgperf] §1.1–1.4.

| Round | Commit    | Change                                                                                                                                                                                          | Measured impact                              |
|------:|-----------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|----------------------------------------------|
| 1     | (pre-`24d76b4` series) | `setvbuf(out_fp, 128 KiB)` + bracketing flush                                                                                                                                          | real ~−3%; reduces fprintf syscall churn     |
| 2     | `24d76b4` + follow-ups | Hash `svg_dict_lookup` (256-slot FNV-1a, open-addressed) + hoist 20-entry `filledsquare/dofilledsquare/...` strcmp guard out of `svg_ps_exec_value` + memoise tokenised `@Graphic` streams | cumulative real −5.3% on top of dict-hash baseline; sys −19% |
| 3     | `2a33e3d` | Hash `svg_ps_exec_op` dispatch: the 151-entry strcmp chain becomes FNV-1a → 256-slot table → `switch (op_id)` (155 op names + 20 `@Graph` plot symbols)                                          | ~77 s → ~32 s wall (−30–45%), user −40–50%   |
| 4     | (round-3 follow-up, landed 2026-05-23) | `svg_glyph_to_unicode` hash table (lookup O(N→1.2 avg probes)) + per-`FONT_NUM` face-flag cache (kills four `strstr` per word) + `SVG_PrintWord` stdio consolidation into one `fprintf` | ~32 s → ~26–29 s wall, user ~−10%            |
| 5     | (round-4, landed 2026-05-23) | Hand-rolled `svg_itoa` / `svg_ftoa3` for page chrome + `SVG_LinkDest` + coord-folded Y-flip drops the per-word `<g>...</g>` wrapper (SVG 17.45 MB → 15.10 MB, −13.5%) + function-pointer dispatch table for the 11 hottest PS ops (`moveto`/`lineto`/`rmoveto`/`rlineto`/`closepath`/`newpath`/`setrgbcolor`/`setgray`/`setlinewidth`/`gsave`/`grestore`) | ~26–29 s → **22–30 s** wall (low-22 best of three), user −5% |

Snippet regression suite holds at **66 Pass-Excellent / 0 Fail** across
all rounds; UG-diff mean SSIM ≥ 0.9234 throughout (no fidelity regression
from any perf change).

## 3. Per-snippet bench overview

The microbenchmark harness in [`tests/bench.py`][benchpy] times each
snippet through `lout` (PS), `lout -G` (SVG), `ps2pdf`, and `rsvg-convert`
in sequence and appends one JSONL record per run to
[`tests/bench.jsonl`][benchjsonl]. [`tests/bench.html`][benchhtml] is a
standalone, dependency-free page that reads the JSONL client-side and
renders an interactive table (sortable columns, per-snippet history
spark-lines, totals row).

Run it with:

```
bash tests/bench.sh        # 62 snippets, ~5 min wall on WSL2
```

Recent sample (one record from 2026-05-22, commit `1c63a39`, 62 snippets,
elapsed 304 s):

| Stage              | Total (s) | Per-snippet median | Notes                                       |
|--------------------|----------:|-------------------:|---------------------------------------------|
| `lout` (PS)        |     9.77  | ~0.10              | frozen `z49.c` reference                    |
| `lout -G` (SVG)    |    11.64  | ~0.12              | currently ~1.2× the PS baseline on snippets |
| `ps2pdf`           |    33.37  | ~0.53              | dominates PDF wall time                     |
| `rsvg-convert`     |    45.21  | ~0.74              | dominates HTML rasterisation                |

The PS-vs-SVG ratio on the snippet corpus is well under the UG ratio
(~1.4× user on `-r3`) because snippets lack the long xref churn that
`-r3` triggers; the snippet corpus is the better signal for changes that
touch the per-emission hot path (text, paths, link rects), while the UG
build is the better signal for changes that touch tokenisation,
cross-references, and per-page chrome.

Historical trend across all bench runs is rendered in
[`tests/snippet_history.html`][snippethist] (sparklines for each
snippet's `svg_sec` across the last N runs).

## 4. DPI sensitivity

Source: [`tests/user_guide_diff/README.md`][ugdiff] §"DPI sensitivity: is
the SSIM floor really irreducible?". Same 327 PS / SVG pages, same
`/tmp/user.ps` and `/tmp/user.svg`, only `pdftoppm -r N` /
`rsvg-convert -d N -p N` change. Reproduce with
`DPI=150 tests/user_guide_diff.sh` or `DPI=200 tests/user_guide_diff.sh`.

| Statistic                                         | 100 dpi | 150 dpi | 200 dpi | Δ 100→150 | Δ 150→200 |
|---------------------------------------------------|--------:|--------:|--------:|----------:|----------:|
| Mean SSIM                                         |  0.9283 |  0.9441 |  **0.9510** | +0.0158 | +0.0069  |
| Median SSIM                                       |  0.9312 |  0.9453 |  0.9518 | +0.0141   | +0.0065   |
| Min SSIM                                          |  0.8455 |  0.8890 |  0.8939 | +0.0435   | +0.0049   |
| Max SSIM                                          |  1.0000 |  1.0000 |  1.0000 |   0       |   0       |
| Pages SSIM ≥ 0.99                                 |  2      |  3      |  3      | +1        |   0       |
| Pages SSIM ≥ 0.95 (visually indistinguishable)    | 49      | 110     | 181     | +61       | +71       |
| Pages SSIM ≥ 0.85 (close)                         | 326     | 327     | 327     | +1        |   0       |
| Pages SSIM < 0.85 (visibly different)             |  1      |  0      |  0      | −1        |   0       |

Interpretation: the 100 → 150 step is the AA floor; the 150 → 200 step
(+0.0069, below the +0.01 "more room to chase" threshold, worst-10 mean
delta dropping from +0.0334 to +0.0107) confirms **200 dpi is the
structural floor**. The residual ~0.05 gap to the theoretical ~0.998
ceiling is pagination drift between Ghostscript and librsvg font
fallback, not antialiasing — see
[`docs/chapter3_pagination_drift_investigation.md`][drift] for the
coordinate-level proof that PS and SVG word x-positions agree
bit-for-bit on the worst pages.

Routine reviews stay at the **100 dpi** baseline for continuity with
prior quarters' tables; cite **0.9441 at 150 dpi** as the headline
secondary number for SVG-back-end change review.

## 5. Outstanding hot spots

From [`tests/profile/README.md`][profile] (post-round-5 gprof snapshot
on the UG `-pg -O3 -no-pie` build):

| Rank | Function                  | %time | self s  | Notes                                                                                  |
|-----:|---------------------------|------:|--------:|----------------------------------------------------------------------------------------|
| 1    | `svg_ps_exec_op`          |  8.73 |  1.62 s | Already hashed (round 3) and table-dispatched for the hot 11 ops (round 5); residual is the cold-switch tail and per-op body cost. |
| 2    | `SVG_PrintBetweenPages`   |  7.38 |  1.37 s | One call per page (306 on UG); inlines `svg_close_page` / `svg_open_page`. Already on `svg_itoa`/`svg_ftoa3` (round 5); remaining cost is the page-level fprintf flush. |
| 3    | `SVG_LinkDest`            |  4.58 |  0.85 s | One `fprintf` per cross-reference target (~1500 on UG). Already converted to itoa/ftoa3 + single `fwrite` (round 5); remaining cost is the per-target buffer assembly. |
| —    | `SVG_RestoreGraphicState` |  3.45 |  0.64 s | Emits `</g>` per `grestore`; called from every `@Graphic` boundary.                    |
| —    | `svg_ps_run`              |  0.92 |  0.17 s | Top loop; very thin now that the dict and op-name lookups are hashed.                  |
| —    | `svg_graphic_concat`      |  0.75 |  0.14 s | Joins multi-token `@Graphic` bodies.                                                   |

General-Lout functions above the SVG layer (`CopyObject` 19.94%,
`DisposeObject` 18.21%, `Manifest` 10.99%, `SearchEnv` 3.93%) dominate
overall and are outside the SVG round's scope.

## 6. Future levers

Ranked roughly by expected wall-time payoff per implementation effort.
Not yet attempted in any round.

1. **NaN-boxing the operand stack.** `svg_value` is currently a tagged
   union with a discriminator byte and 16 B of payload (double / int /
   pointer / etc.); a NaN-boxed encoding would pack number + type into
   8 B and let the hot stack ops (`dup`, `pop`, `exch`, `index`,
   `roll`) memcpy half the bytes. Cache-line pressure inside
   `svg_ps_run` is the next-most-likely cliff once item 2 below lands.
2. **More aggressive `@Graphic` translation.** Today the embedded PS
   interpreter still treats raw `@Graphic` bodies that don't start
   with `<` as PS to evaluate (and emits an XML comment for the
   uncovered subset). A peephole compiler over the tokenised stream
   could collapse common prologue idioms (`x y moveto x' y' lineto
   stroke` → single `<line>`) without going through the operand
   stack — saves both per-op dispatch and stack churn. See
   [`lout/SVG_PORTING.md`][porting] §"PostScript op translation" for
   the running map of which prologue procedures are already special-
   cased and which still go through the generic exec loop.
3. **String interning for dict keys.** Round 2 hashed the dict but
   the comparison inside each bucket is still `strcmp`. An intern
   table at parse time (one global FNV table feeding canonical
   `const char *`) reduces every bucket compare to a pointer equality
   check and also speeds the residual strcmp clusters in
   `svg_ps_exec_value` (predicates, type tests). Projected 3–5%
   additional based on the gprof line for `strcmp` (not currently a
   top-20 entry but appears in the cumulative inclusive time of
   every name lookup).
4. **`SVG_RestoreGraphicState` batching.** Adjacent `grestore` /
   `gsave` pairs are common at `@Graphic` boundaries; emitting one
   `</g><g …>` instead of `</g>\n<g …>` (and skipping pairs entirely
   when the saved state is structurally identical to the restored
   one) drops both bytes and `<g>` nesting depth.
5. **`<defs>` extraction of repeating per-font `<g>` family
   attributes.** Round 4's face-flag cache eliminated the per-word
   `strstr` cost but each `<text>` still re-states its
   `font-family`/`font-weight` literally. A `<defs>`-emitted
   `<g class="…">` wrapper used as `<use>` reference would compress
   the output further and reduce flush bytes.
6. **Reduce `svg_dict_gc_sweep` frequency.** Currently runs at the
   end of every `svg_ps_run`. Below 0.4% in gprof so the payoff is
   small, but trivially safe: gate on `svg_dict_pool_used` crossing
   a high-water mark instead of running unconditionally.

Items 2 and 3 in particular are tracked in
[`lout/SVG_PERFORMANCE.md`][svgperf] §4 (the original ranked
optimisation table) and would close the remaining wall-time gap
between SVG and PS user CPU on the `-r3` UG build.

[svgperf]: ../lout/SVG_PERFORMANCE.md
[porting]: ../lout/SVG_PORTING.md
[profile]: ../tests/profile/README.md
[benchpy]: ../tests/bench.py
[benchhtml]: ../tests/bench.html
[benchjsonl]: ../tests/bench.jsonl
[snippethist]: ../tests/snippet_history.html
[ugdiff]: ../tests/user_guide_diff/README.md
[drift]: chapter3_pagination_drift_investigation.md
