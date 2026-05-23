# mdlout v0.2.4 — sub-23s UG build, ligatures, expert PS recovery

Released: 2026-05-23
Companion submodule tag: `lout/svg-backend-v0.2.4`
   (https://github.com/jclements3/lout, branch `svg-backend`,
    commit f234cde).

Post-v0.2.3 release, same calendar day. A focused perf + tests-
hygiene cut: `z53.c` perf round 4 drops the User's Guide single-pass
SVG build from 41.2 s real / 35.4 s user (v0.2.2 baseline) to
22.6 s real / 19.8 s user (-45% wall, -13.5% SVG output size on
`doc/user/all`); the `tests/lout_doc_renders/expert` SSIM recovers
from 0.7061 (concurrent-runner damage on shared cross-reference
files; mis-attributed to back-end drift on the v0.2.3 landing page)
to 0.9202 once the per-run scratch-dir fix lands in the refreshed
renders; and the User's Guide PS-vs-SVG mean SSIM ticks up from
0.9234 to 0.9278 as a side effect of the round-4 coord fold
collapsing a per-word `<g>` wrapper that was costing sub-pixel
rounding error on the rsvg side.

`z49.c` (PostScript) and the legacy PDF path remain frozen and
bit-identical to v0.2.0. mdlout package version is unchanged at
0.2.3; the next mdlout-surface change will carry both a PyPI
release and a tag bump (PR #154 is still in flight, hence the
"if landed" caveat in the cut prompt).

## Headlines

- **[lout] `z53.c` perf round 4 -- 22.6 s real on the User's
  Guide.** Three changes from the v0.2.3
  `tests/profile/gprof_z53_hot.txt` hot-spot report:
  (1) hand-rolled `svg_itoa` / `svg_ftoa3` in
  `SVG_PrintBetweenPages` (7.38% / 1.37 s self) and `SVG_LinkDest`
  (4.58% / 0.85 s self), replacing three `fprintf` calls per
  page/link with direct buffer fills plus one `fwrite`;
  (2) coord-folded Y-flip on text emission -- the per-word
  `<g transform="translate(x,y) scale(1,-1)">` wrapper is gone,
  replaced by an inline `transform="matrix(1 0 0 -1 x y)"` on the
  `<text>` element (-13.5% SVG output size on the User's Guide,
  ~470 lines off `user.svg`);
  (3) function-pointer dispatch table for the 11 hottest / simplest
  PS ops (`newpath`, `moveto`, `lineto`, `rmoveto`, `rlineto`,
  `closepath`, `setrgbcolor`, `setgray`, `setlinewidth`, `gsave`,
  `grestore`); cold ops still flow through the legacy switch in
  `svg_ps_exec_op`. Combined with the round-3 stdio buffering and
  initial hash-op-dispatch tightening that landed earlier in
  v0.2.3 (`f1fdd77`), the cumulative perf curve is:

      v0.2.2 baseline (round 2):    41.2 s real / 35.4 s user
      v0.2.3 round 3 mid-cycle:     ~30 s real / ~25 s user
      v0.2.4 round 4 (this cut):    22.6 s real / 19.8 s user

  -45% wall time over two releases. ROADMAP's v0.4 sub-30s target
  is fully cleared; the original v0.2 target of "feels live" for
  iterative authoring is now real.

- **`tests/lout_doc_renders/expert` SSIM 0.7061 -> 0.9202.** The
  per-run scratch-dir fix in `build.sh` from v0.2.3 (reverses
  concurrent-runner damage when two agents run the suite in the
  same checkout, scribbling on each other's `*.li` / `*.ldx` /
  `lout.lix` cross-reference state) only takes effect on
  re-rendered output. v0.2.3 shipped the fix but did not refresh
  the renders that the landing page cites, so the v0.2.3 expert
  row showed up as `ssim-diff` red (0.7061) even though the
  back-end output was fine. This release re-runs all four docs
  with the fixed isolation:

      design:    0.9123 -> 0.9190    (ssim-ok, unchanged class)
      expert:    0.7061 -> 0.9202    (ssim-diff -> ssim-ok)
      slides:    0.9804  unchanged   (ssim-good)
      user:      0.9292  unchanged   (ssim-ok)

  `expert.pdf` grows from 478,385 to 507,915 bytes (+6.2%): the
  v0.2.3 in-doc `@BackEnd @Case` SVG-arm fix caused a real layout
  shift in the Expert's Guide (the SVG arm picks up a peer
  `@Yield` body), so the previous PS render was diverging from
  the post-fix SVG. Re-rendering through the fixed pipeline
  re-aligns them.

- **`tests/user_guide_diff` mean SSIM 0.9234 -> 0.9278.** Same
  327-page PS-vs-SVG diff over `doc/user/all`, re-rendered after
  the round-4 coord fold. Distribution shifts:

      Mean SSIM:               0.9234 -> 0.9278
      Median SSIM:             0.9258 -> 0.9309
      Pages SSIM >= 0.99:           2 -> 2
      Pages SSIM >= 0.95:          36 -> 47   (+30%)
      Pages SSIM >= 0.85:         324 -> 326
      Pages SSIM <  0.85:           3 -> 1    (-67%)

  The improvement is mechanical: packing the Y-flip into an
  inline matrix on each `<text>` removes a per-word group
  nesting level that was costing sub-pixel rounding error when
  rsvg flattened the transform stack. No back-end behaviour
  change; the PS reference is bit-identical to v0.2.3.

## Regression status

- 65-snippet single-feature suite: 0 Fail, 100% Pass-Excellent
  under the post-v0.2 tightened thresholds (5% AE for text,
  2% AE / SSIM 0.95 for graphics-heavy). Unchanged from v0.2.3.
- `tests/lout_doc_renders/` landing page: all four docs render
  cleanly through `z53.c`; expert moves into the `ssim-ok` band
  (0.85 <= SSIM < 0.95). Zero residual SVG `@Case` warnings
  across `doc/{design,expert,slides,user}`.
- `tests/user_guide_diff/`: mean SSIM 0.9278 (was 0.9234),
  median 0.9309 (was 0.9258), 47 visually-indistinguishable
  pages (was 36).
- `bash tests/browser_test.sh`: 53-55 PASS / 0 FAIL across the
  cycle. Unchanged from v0.2.3.
- PostScript / `--format=pdf` output bit-identical to v0.2.3 for
  the example corpus and `doc/user/all`. `expert.pdf` size
  grows for the layout-shift reason above (still a v0.2.3
  back-end fix, surfaced now via re-render).

## Compatibility / migration

- mdlout package version unchanged at 0.2.3. `pip install mdlout`
  (once PyPI publish lands) will continue to resolve the v0.2.3
  wheel until PR #154's bump lands.
- No CLI flag changes. The v0.2.3 `--no-subset-fonts` opt-out,
  `--dark[=force|auto]` cascade, and the four passthrough macros
  (`@Math` / `@DMath` / `@ABC` / `@SVG` / `@SVGFile`) are
  unchanged.
- Re-render to pick up the round-4 SVG output reduction. The
  `<g transform="translate(x,y) scale(1,-1)">` wrapper has been
  removed from the SVG; downstream tooling that string-greps for
  it (none known) will need to look for
  `transform="matrix(1 0 0 -1 ...)"` on the `<text>` element
  instead.

## How to publish the GitHub release (manual instructions)

The release is being published from the v0.2.4 tag on `main`. If
`gh release create v0.2.4 --notes-file docs/RELEASE_NOTES_v0.2.4.md
--latest` succeeds in this run, no further action is required.

If `gh` rejects the create call for OAuth-scope reasons:

1. Push tags and commits:

       git push origin main
       git push origin v0.2.4

2. Publish the release:

       gh release create v0.2.4 \
         --title "v0.2.4 — sub-23s UG build, ligatures, expert PS recovery" \
         --notes-file docs/RELEASE_NOTES_v0.2.4.md \
         --latest

3. The companion submodule tag `svg-backend-v0.2.4` should already
   be on the `fork` remote (jclements3/lout) and point at commit
   `f234cde` on branch `svg-backend`. If not, from inside the
   submodule:

       cd lout
       git push fork svg-backend-v0.2.4

Full per-entry details: see
[CHANGELOG.md](../CHANGELOG.md#024---2026-05-23).
