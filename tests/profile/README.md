# SVG Back-End Profile (post perf-round-2)

Snapshot of `gprof` data collected on the User's Guide SVG build with
the current `svg-backend` head of the lout submodule.  Baseline wall
time before this profile (optimised `-O3` build, single pass through
`doc/user/all`): **~25.83 s user** (per the perf-round-2 entry in
`lout/SVG_PERFORMANCE.md`, plus a few seconds of WSL2 noise on this
host).  The instrumented `-pg -O3 -no-pie` build runs in ~22 s user
because gprof's mcount overhead is small relative to the page-emission
fprintf cost.

## Reproducing

```bash
bash tests/profile_ug_build.sh
```

The script rebuilds `lout/lout` with `-pg -fno-omit-frame-pointer`,
runs a single SVG pass under that binary, and writes three reports
into this directory.  It restores the optimised binary on exit (unless
`MDLOUT_PROFILE_KEEP_PG=1`) so the regression suite stays clean.
Wall time end-to-end is ~90 s.

Only profiler available on this host (perf and valgrind are not
installed; check `which perf valgrind` if reproducing elsewhere):

  1. `perf`    -- not installed.
  2. valgrind  -- not installed.
  3. **gprof** -- used here.
  4. clock_gettime fallback -- unused; gprof is sufficient.

## Files

  * `gprof_full.txt`   -- full report (flat + call graph).
  * `gprof_brief.txt`  -- `gprof -b`, flat profile only.
  * `gprof_z53_hot.txt`-- just the `SVG_*` / `svg_*` rows from the
    flat profile, sorted by self-time descending.
  * `build.log`        -- output of the `-pg` rebuild (for diagnosing
    link-time issues such as missing `-no-pie`).

## How to read the flat profile

The columns are: `%time, cumulative_seconds, self_seconds,
calls, self us/call, total us/call, name`.  For the SVG dispatch
functions (`SVG_PrintBetweenPages`, `SVG_PrintWord`, `SVG_LinkDest`,
`SVG_RestoreGraphicState`, ...) the `calls` column is empty: they are
invoked through the `BACK_END` function-pointer table in `z01.c`, so
gprof's `__mcount` cannot attribute a caller and lists them as
`<spontaneous>` in the call graph.  Self-time is still correct.

`svg_ps_exec_op` is similarly listed without a caller because it is
called from `svg_ps_run` via an op_id switch after the hash dispatch
landed in commit `2a33e3d`.  Inlining at `-O3` flattens
`svg_close_page`/`svg_open_page` into `SVG_PrintBetweenPages`, which
is why that function shows ~1.4 s of self-time despite being three
lines of source.

## Top 3 hot functions in z53.c

From `gprof_z53_hot.txt`:

| Rank | Function                  | %time | self s | Notes                                            |
|-----:|---------------------------|------:|-------:|--------------------------------------------------|
| 1    | `svg_ps_exec_op`          | 8.73  | 1.62   | 151-case PostScript op switch (already hashed)   |
| 2    | `SVG_PrintBetweenPages`   | 7.38  | 1.37   | called once per page (306), inlines `svg_close_page` / `svg_open_page` (fprintf + setvbuf flushes) |
| 3    | `SVG_LinkDest`            | 4.58  | 0.85   | one `fprintf` per cross-reference target         |

Honourable mentions:

  * `SVG_RestoreGraphicState`  3.45 %  0.64 s -- emits `</g>` per `grestore`; called from every `@Graphic` boundary.
  * `svg_ps_run`               0.92 %  0.17 s -- the interpreter top loop; very thin because most work was hashed away.
  * `svg_graphic_concat`       0.75 %  0.14 s -- joins multi-token `@Graphic` bodies; called once per @Graphic.

General-Lout functions above the SVG layer dominate overall
(`CopyObject` 19.94 %, `DisposeObject` 18.21 %, `Manifest` 10.99 %,
`SearchEnv` 3.93 %) but those are outside the scope of this profile.

## Next-round optimisation candidates

Ranked by impact-per-effort, given the data above:

  1. **fprintf -> direct write_buffer for the per-page chrome.**
     `SVG_PrintBetweenPages` (#2) and `SVG_LinkDest` (#3) together burn
     ~2.2 s on fixed-shape fprintf calls (page open/close tags, link
     rect with three doubles, four integers).  Replacing these with a
     hand-rolled `itoa`/`ftoa3` into a local buffer + a single
     `fwrite` should save 1.0-1.5 s wall (5-7 %).  `svg_outbuf` is
     already 128 KB so the `setvbuf` win is realised, but each fprintf
     still does the format-string parse.
  2. **Bypass the bottom-left -> top-left wrapper `<g>` on glyph emission.**
     `SVG_PrintWord` (currently ~0.02 s self time but every call emits
     `<g transform="translate(...) scale(1,-1)"><text ...>...</text></g>`,
     which doubles the bytes per word).  Coordinate-fold at emit time
     (subtract from page height once, no `<g>`) would shrink the SVG
     by ~25 % and save another fprintf per word.  Output-size pressure
     also reduces `SVG_PrintBetweenPages` flush cost.
  3. **op_id -> table-of-handlers for the hot PostScript ops.**
     `svg_ps_exec_op` is already hashed for name resolution but still
     has a giant `switch (op_id)` body.  For the ~20 ops that account
     for >95 % of `svg_ps_run` exec calls (`moveto`, `lineto`,
     `rmoveto`, `rlineto`, `setrgbcolor`, `setlinewidth`, `gsave`,
     `grestore`, `stroke`, `fill`, ...), a function-pointer dispatch
     table cuts branch-mispredict cost.  Expected: ~0.3-0.5 s (2 %).

Items 4-5 from `lout/NEXT_OPTIMIZATIONS.md` (Symbol-font glyph table,
@Graph `symbolsize`) are correctness, not performance, and are not
visible here.

Total achievable wall delta on the User's Guide build for the three
above: roughly **-10 % over the current ~25.8 s user baseline**, i.e.
landing in the low-23 s range.  Further gains require attacking the
general-Lout functions (`CopyObject` / `DisposeObject` / `Manifest`),
which is out of scope for the SVG round.
