# z53.c internals -- a contributor's tour of the SVG back end

This document is the missing orientation guide between
[`docs/ARCHITECTURE.md`](ARCHITECTURE.md) (which sketches the whole
mdlout pipeline) and the back-end-specific trackers
[`lout/SVG_PORTING.md`](../lout/SVG_PORTING.md),
[`lout/SVG_PERFORMANCE.md`](../lout/SVG_PERFORMANCE.md), and
[`lout/NEXT_OPTIMIZATIONS.md`](../lout/NEXT_OPTIMIZATIONS.md). Those
trackers describe ongoing work; this file explains the code as it
currently stands so a new contributor can read `lout/z53.c` (~5700 LOC)
without losing the plot.

The reader is assumed to know that Lout exists (a batch typesetter that
emits PostScript), that PostScript is a stack-based drawing language,
and that SVG is XML with affine transforms and path data. Familiarity
with `lout/z49.c` (the PostScript back end) is helpful but not required.

## 1. Where z53.c fits

Lout's front half -- lexer, parser, object system, galley engine, font
service, hyphenator, language layer, error reporter -- is back-end
agnostic. Everything from input bytes to fully-laid-out pages happens in
modules `z01`-`z48` and `z50`-`z52` regardless of which back end is
selected. The back end's job is to walk Lout's final tree, receive
roughly 26 emission callbacks, and produce a byte stream.

z53.c is one of four such back ends:

| Module | Selected by  | Emits          | Status                |
|--------|--------------|----------------|-----------------------|
| z49.c  | (default)    | PostScript     | **frozen**            |
| z48.c / z50.c | `-p`  | PDF directly   | dormant in this fork  |
| z51.c  | `-S`         | plain text     | stable                |
| z53.c  | `-G`         | SVG (per page) | active development    |

Selection is done in `z01.c:689-705` (the back-end dispatch table). Both
the SVG back end (`SVG_BackEnd`) and its no-op twin (`SVG_NullBackEnd`)
are exported from z53.c; z01.c switches the live pointer between the
two as it does for the PostScript pair, with the null version used
during the non-final cross-reference passes so xref resolution can run
without emitting megabytes of throwaway SVG. `SVG_BackEnd` is built at
`lout/z53.c:5515` and `SVG_NullBackEnd` at `lout/z53.c:5659`.

The `BACK_END` interface itself is defined in `lout/externs.h:2073-2118`:
a `struct back_end_rec` of nine BOOLEAN feature flags and 26 function
pointers. z53.c populates every slot; nothing about the rest of Lout
changes when `-G` is on. Critically, z53.c **reuses** Lout's existing
font metrics (`finfo[]`, `FontFamily`, `FontFace`, `FontSize`,
`FontHalfXHeight`, `FontMapping`), colour service (`ColourCommand`,
`COLOUR_NUM`), and texture machinery -- only the emission layer differs.

## 2. The 26 BACK_END callbacks

The full list, in `struct back_end_rec` order, with the entry-point line
numbers in z53.c. One-paragraph summaries follow.

| Callback                  | Line in z53.c | Role                                  |
|---------------------------|---------------|---------------------------------------|
| `PrintInitialize`         | 109           | open output stream, write XML preamble |
| `PrintLength`             | 831           | format a length string                |
| `PrintPageSetupForFont`   | 843           | (no-op in SVG)                        |
| `PrintPageResourceForFont`| 847           | (no-op in SVG)                        |
| `PrintMapping`            | 850           | (no-op in SVG)                        |
| `PrintBeforeFirstPage`    | 856           | open first page, ingest prepends      |
| `PrintBetweenPages`       | 864           | close one page, open next             |
| `PrintAfterLastPage`      | 872           | close final page, flush, shut down PS |
| `PrintWord`               | 894           | emit one `<text>` glyph run           |
| `PrintPlainGraphic`       | 956           | (no-op; flag is FALSE in this back end) |
| `PrintUnderline`          | 969           | emit `<line>` for word underlining    |
| `CoordTranslate`          | 1066          | open `<g transform="translate(...)">` |
| `CoordRotate`             | 1085          | open `<g transform="rotate(...)">`    |
| `CoordScale`              | 1103          | open `<g transform="scale(...)">`     |
| `CoordHMirror`            | 1116          | open `<g transform="matrix(-1,0,0,1,0,0)">` |
| `CoordVMirror`            | 1121          | open `<g transform="matrix(1,0,0,-1,0,0)">` |
| `SaveGraphicState`        | 1030          | push gs level (counts opened groups)  |
| `RestoreGraphicState`     | 1052          | close every group at the current level |
| `PrintGraphicObject`      | 5219          | run the embedded PS interpreter       |
| `DefineGraphicNames`      | 5275          | capture xsize/ysize/xmark/ymark/font  |
| `SaveTranslateDefineSave` | 5325          | sequence of save+translate+define+save |
| `PrintGraphicInclude`     | 5348          | emit `<image href>` (raster/SVG)      |
| `LinkSource`              | 5461          | emit `<a xlink:href="#id">` overlay   |
| `LinkDest`                | 5474          | emit `<a id="id">` anchor             |
| `LinkURL`                 | 5491          | emit `<a xlink:href="url" target="_blank">` |
| `LinkCheck`               | 5504          | (no-op in SVG)                        |

A few deserve a longer note.

### PrintInitialize / open_page / close_page

`SVG_PrintInitialize` (z53.c:109) records the FILE pointer, resets every
module-static, seeds the outer-CTM tracker to identity, calls
`svg_psinterp_init` to spin up the embedded PS interpreter, attaches a
128 KiB fully-buffered I/O buffer with `setvbuf`, and writes the XML
prolog. The 128 KiB `svg_outbuf[]` is module-static (z53.c:107) rather
than stack-allocated because `setvbuf` requires the buffer to outlive
the stream.

Per-page emission is `svg_open_page` (z53.c:153) and `svg_close_page`
(z53.c:190). The page open emits a `<svg viewBox>` sized in points,
then a `<defs>` block with all eight named textures (see section 6),
then a single page-level `<g transform="matrix(1 0 0 -1 0 H)">` that
flips Y so the body of the page can use literal Lout (bottom-left)
coordinates without per-element Y inversion. Close mirrors that:
`</g></svg>`.

### PrintWord

`SVG_PrintWord` (z53.c:894) is the hot path that emits 90+% of bytes in
a typical document. The glyph emission strategy is described in section 5;
mechanically, the function builds a `<g transform="translate(x,y)
scale(1,-1)">` counter-flip wrapper (because the page-level group has
already flipped Y; without the counter-flip glyphs would render
upside-down), then writes a `<text x="0" y="0" font-family="..."
font-size="...">` with optional `font-weight="bold"` /
`font-style="italic"` deduced by `strstr` on the FontFace string
("Bold", "Italic", "Slope", "Oblique") and optional `fill` from
`ColourCommand` via `svg_colour_rgb` (z53.c:212).

### CoordTranslate / Rotate / Scale / HMirror / VMirror

Each opens a fresh `<g transform="...">` group via the helper
`svg_open_transform_g` (z53.c:998), which increments `gs_groups[gs_top]`
so the matching `RestoreGraphicState` knows how many `</g>` tags to
close. Translate / rotate / scale **also** update two parallel data
structures:

1. The module-static outer CTM (`svg_outer_ctm` in z53.c:75), so the
   embedded PS interpreter can be seeded with the actual page-level
   coordinate frame each time `PrintGraphicObject` invokes it.
2. The persistent interpreter's gs stack via the
   `svg_ps_module_translate` / `_rotate` / `_scale` helpers
   (z53.c:2506, :2513, :2524). This is how PS-level
   transform / itransform round-trips see the correct frame.

Lout's positive rotation is counter-clockwise; SVG's is clockwise *in
the default top-left coordinate system*. But because every page lives
inside the Y-flip group, the in-page coordinate system is bottom-left
and rotation is therefore CCW for positive angles, matching Lout. **No
angle negation is needed in this back end** (see comment at z53.c:1090).
This is one of the simplifications enabled by the page-level Y-flip.

### SaveGraphicState / RestoreGraphicState

The graphics state stack is just an array of integers
(`gs_groups[SVG_MAX_GS]` at z53.c:65): each entry counts how many
`<g transform>` groups were opened at that save level. `SaveGraphicState`
also snapshots the outer CTM into `svg_outer_ctm_stack[gs_top]`
(z53.c:1044) and calls `svg_ps_module_gsave`. `RestoreGraphicState`
unwinds: writes `gs_groups[gs_top]` close tags, restores the CTM,
decrements gs_top, calls `svg_ps_module_grestore`.

### PrintGraphicObject

`SVG_PrintGraphicObject` (z53.c:5219) is where the embedded PS
interpreter is actually invoked. The full pipeline is described in
section 7.

### DefineGraphicNames

`SVG_DefineGraphicNames` (z53.c:5275) captures the seven numerics that
the PostScript back end binds at the top of every `LoutGraphic`
procedure body: `xsize`, `ysize`, `xmark`, `ymark`, `loutf`, `loutv`,
`louts`. In PS mode the values are computed by `z49.c` then emitted as
PS code; in SVG mode they're stored in module statics
(`cur_gr_xsize` ... `cur_gr_louts`, z53.c:81-84) which the PS
interpreter reads via `svg_ps_resolve_value` (z53.c:2540) when it sees
those names in a graphic body. The function also propagates the
current Lout colour into the interpreter's gstate fill/stroke (see
z53.c:5307).

### LinkSource / LinkDest / LinkURL

All three thin wrappers over `svg_emit_link_rect` (z53.c:5446) which
emits a fill-none `<rect>` sized to the bbox. `LinkSource` wraps that
rect in `<a xlink:href="#ID">` (z53.c:5461), `LinkDest` wraps it in
`<a id="ID"><rect width="0" height="0"/></a>` (z53.c:5474), `LinkURL`
wraps it in `<a xlink:href="URL" target="_blank">` (z53.c:5491). ID
sanitisation (alphanumerics only, `_` substitute, `LOUT` prefix) is
`svg_emit_link_id` at z53.c:5422.

## 3. Coordinate system handling

Lout uses bottom-left-origin points internally; one PT is 20 internal
units (see `PT` macro in `externs.h`). SVG uses top-left-origin user
units (defaulting to CSS px but switchable via `viewBox`+`width`
attributes to points).

The bridge is a **single page-level Y-flip**, emitted once in
`svg_open_page` at z53.c:179:

```
<g transform="matrix(1 0 0 -1 0 H)">
```

where `H` is the page height in points. Inside this group the local
coordinate system is bottom-left in points -- identical to Lout's. Every
subsequent emission can use raw Lout coordinates divided by `PT`.

The wrinkle is that `<text>` glyphs inside a Y-flipped group render
upside-down. The fix (used in both `SVG_PrintWord` and the PS
interpreter's `svg_ps_show` helper at z53.c:2897) is to wrap each text
emission in a counter-flip:

```
<g transform="translate(x,y) scale(1,-1)">
  <text x="0" y="0" ...>...</text>
</g>
```

`SVG_PrintGraphicInclude` (z53.c:5348) applies the same trick to raster
images, because PNG/JPG are top-left-origin natively (z53.c:5395).

The viewBox is emitted in points: `viewBox="0 0 W H"` where W and H are
the page extent in points and the `width`/`height` attributes carry the
explicit `pt` unit (z53.c:170). Page label (from Lout's `@PageLabel`)
goes into `data-label="..."` so JavaScript can find pages by label.

## 4. The embedded PostScript interpreter

This is the heart of the back end and consumes roughly 4000 of the
5700 lines. Its purpose: Lout's standard library and prelude
(`diagf.lpg`, `graphf.lpg`, `coltex`, the `@Box` / `@Rule` /
`@ShadowBox` glue, every @SysPrependGraphic file) emits PostScript
fragments that the original z49.c just splices into the output. SVG
has no such "splice raw PS" escape hatch, so z53.c contains a
mini-interpreter that runs PostScript and emits SVG drawing operators
instead.

It is **deliberately incomplete** -- it implements the operator subset
that Lout's prologue and standard library actually use, plus the bits
of @Diag / @Graph / @Fig that the test suite exercises. Operators
outside that set produce an "unknown PostScript operator" warning on
the first eight occurrences (z53.c:4925) and an XML comment fallback in
the output.

### 4.1 Stack and dict-stack structures

The operand stack is fixed-size, on the interpreter state:

```c
typedef struct svg_ps_state {
  svg_value  stack[SVG_PS_STACK_DEPTH];   /* 512 entries */
  int        top;
  svg_gstate gs[SVG_PS_GS_DEPTH];         /* 32-deep gsave/grestore */
  int        gs_top;
  /* path accumulator, cur_x/cur_y, last_xp/yp, have_cp, had_geom */
} svg_ps_state;
```

(definition at z53.c:1350; sizes at z53.c:45-49). The module-persistent
instance lives at z53.c:1391 (`g_psstate`) -- one per document, surviving
across @Graphic invocations.

`svg_value` (z53.c:1297) is a tagged union of NULL, NUM, BOOL, NAME,
LITNAME, STRING, PROC, ARRAY, MARK, DICT. Names, strings, procs and
arrays own arena-allocated backing buffers, all freed in one shot by
`svg_arena_free_all` (z53.c:1432) when the interpreter shuts down.

The **dict pool** is a fixed array of dictionaries, slot 0 being
userdict:

```c
static svg_dict   svg_dict_pool[SVG_PS_DICT_POOL];      /* 1024 dicts  */
static int        svg_dict_stack[SVG_PS_DICT_STACK_DEPTH]; /* 32 deep */
```

(z53.c:1335-1337). Each `svg_dict` has 512 fixed slots, open-addressed.
A dict is "allocated" by flipping its `in_use` flag (`svg_dict_alloc`,
z53.c:1476). The pool is also subject to mark-and-sweep GC -- see 4.5.

### 4.2 svg_dict_lookup -- FNV-1a + open addressing

`svg_dict_lookup` (z53.c:1536) and its define companion
`svg_dict_def` (z53.c:1499) implement a 512-slot open-addressed hash
table keyed on FNV-1a 32-bit of the byte string. The hash function is
`svg_name_hash` (z53.c:1452):

```c
static unsigned int svg_name_hash(const char *s)
{
  unsigned int h = 2166136261u;
  while( *s ) { h ^= (unsigned char) *s++; h *= 16777619u; }
  return h;
}
```

Linear probing on collision. No tombstones, because the only delete is
`svg_dict_clear` which zeros the whole table. Slot count is
`SVG_PS_DICT_ENTRIES = 512` (a power of 2; `& MASK` rather than `%`).

The cached hash on each entry (`svg_dict_entry.hash`, z53.c:1316)
short-circuits the probe loop: a slot is a miss if either name is NULL
or hashes differ; only on a hash match does the strcmp fire. This is
the same pattern used for the op-id table in 4.3.

Why hashed at all: before this change `svg_dict_lookup` was a linear
scan over up to 512 slots, and the User's Guide build does ~10^7
lookups per pass. The hash brought the dict lookup cost down by about
25-30% of total wall time -- see `lout/SVG_PERFORMANCE.md` for the
profile traces.

`svg_dict_stack_lookup` (z53.c:1566) walks the dict stack top-to-bottom
calling `svg_dict_lookup` per level, exactly matching PostScript
semantics.

### 4.3 svg_ps_exec_op -- hashed op-id dispatch

`svg_ps_exec_op` (z53.c:3213) is the giant `switch` over every built-in
operator. The dispatch is two-step:

1. `svg_op_lookup(name)` (z53.c:3193) reads a 256-slot FNV-1a hashed
   table of `(name, op_id)` pairs and returns an `svg_op_id` enum
   value (or `SVG_OP_NONE`).
2. A single `switch( op_id )` runs the case body.

The seed table is `svg_op_seed[]` at z53.c:3058 -- roughly 175 entries.
Construction is lazy: `svg_op_hash_build` (z53.c:3168) runs on the
first call to `svg_op_lookup`, FNV-1a hashes every seed name, and
inserts with linear probing into `svg_op_hash_table[]` (z53.c:3052).

Measured impact (recorded in `lout/SVG_PERFORMANCE.md`): switching
from the previous chain of 150+ strcmps to hashed dispatch cuts the
single-pass User's Guide build from ~77 s to ~32 s wall, a ~58%
reduction. That number rolls in the other recent items
(`filledsquare` hoist, `setvbuf`, @Graphic token memoisation) but the
hashed op-id dispatch is the dominant contributor.

#### Alias collapsing

The seed table deliberately maps multiple names to the same `op_id`
where the case body is identical:

- `setrgbcolor` and `LoutSetRGBColor` -> `SVG_OP_SETRGBCOLOR` (z53.c:3066)
- `setgray` and `LoutSetGray` -> `SVG_OP_SETGRAY` (z53.c:3067)
- `fill` and `eofill` -> `SVG_OP_FILL` (z53.c:3065)
- `setlinecap`, `setlinejoin`, `setmiterlimit` -> `SVG_OP_SETLINESTYLE` (z53.c:3071-3072)
- `currentmatrix` and `defaultmatrix` -> `SVG_OP_CURRENTMATRIX` (z53.c:3080)
- `userdict`, `systemdict`, `globaldict`, `errordict`, `statusdict`,
  `$error` all collapse to `SVG_OP_SYSDICT` (z53.c:3120-3122) because
  this interpreter doesn't distinguish them; the same case body just
  pushes a stand-in dict handle.
- `save_cp` and `restore_cp` both map to `SVG_OP_SAVE_CP` (z53.c:3113)
  -- they're the prologue's no-ops for currentpoint save/restore.

Where the case body discriminates on the original name, the aliases
keep distinct op_ids:

- `arc` and `arcn` are separate (`SVG_OP_ARC` / `SVG_OP_ARCN`,
  z53.c:3064) because `svg_ps_arc` (z53.c:2179) takes a CCW/CW flag.
- `eq` / `ne`, `lt` / `gt` / `le` / `ge`, `and` / `or` / `xor` all get
  distinct ids (z53.c:3129-3132); their bodies branch differently.

This pattern matters when adding new operators: if two names truly
share a body, collapse to one op_id and use the seed table to alias.
If the body needs to know which name was called, give each a distinct
op_id even though they share a switch case (using fall-through is
fine).

### 4.4 Control flow operators

PostScript control flow is implemented in `svg_ps_exec_op` and works
through two module-static flags:

- `svg_exit_flag` (z53.c:1346) -- set by `exit` to short-circuit out of
  the current `loop` / `repeat` / `for` / `forall` body. Cleared when
  the enclosing iterator unwinds.
- `svg_stop_flag` (z53.c:1347) -- set by `stop`, cleared only by a
  matching `stopped` (which catches the stop and pushes a boolean
  result).

The implemented operators are:

- `if` -- `<bool> <proc> if`: run proc if bool is true.
- `ifelse` -- `<bool> <procT> <procF> ifelse`: run one branch.
- `for` -- `<init> <step> <limit> <proc> for`: classic counted loop
  pushing the index before each iteration.
- `forall` -- iterate over an array/proc/string, pushing each element.
- `loop` -- run proc forever until `exit` (or `svg_stop_flag`).
- `repeat` -- `<n> <proc> repeat`: run proc n times.
- `exit` -- set `svg_exit_flag = 1`.
- `stop` -- set `svg_stop_flag = 1`.
- `stopped` -- `<proc> stopped <bool>`: run proc with stop-trap, push
  true if it stopped, false otherwise.

All the iteration operators consult `svg_exit_flag` per-iteration and
`svg_stop_flag` per-step, so the interpreter unwinds cleanly. There's
also a recursion-depth guard (`svg_recursion_depth`,
`SVG_PS_MAX_RECURSION = 256`, z53.c:51) that flips `svg_stop_flag` to
abort runaway prologues -- this fires on the User's Guide build only
if the dict pool is exhausted in a way that triggers infinite
look-ups (it shouldn't, post-GC).

### 4.5 Mark-and-sweep dict GC

The Lout @Diag prologue exercises the `N dict begin ... end` idiom
heavily -- one dict per node, link, label, arrowhead. The naive
strategy of "free on `end` if the dict is no longer referenced"
(implemented at `svg_dict_try_free_anonymous`, z53.c:1612) cannot
catch every leak: `ldiagpushtagdict` / `ldiagpoptagdict` briefly leave
the popped dict on the operand stack as part of a `currentdict end dup
/ldiagtagdict known { exit } if` loop, so the on-`end` check
(correctly) refuses to reclaim the slot, and the slot then drifts
unreferenced indefinitely.

After ~60 @Diag instances the 1024-slot pool ran dry, subsequent
`dict` calls returned -1, and the entire `ldiagdosegpath` connector
path silently degraded -- the famous "thin connector strokes
disappear" regression documented at length in
[`tests/user_guide_diff/README.md`](../tests/user_guide_diff/README.md)
and `lout/SVG_PORTING.md` lines 575-610.

The fix is a proper mark-and-sweep collector:
`svg_dict_gc_sweep` at z53.c:1694. Roots are the dict stack and the
operand stack; reachability is transitive via `svg_dict_mark`
(z53.c:1645) which recurses through array/proc items and dict slot
values. Anything `in_use` but unmarked gets reclaimed.

The sweep runs **once at the end of every `svg_ps_run`** (z53.c:5112)
-- not per-operator. That's coarse enough to be cheap (one pass over
~1024 dicts per @Graphic) and frequent enough that pool_used stays
bounded indefinitely. Measured post-fix: ~2200 0.48-point connector
strokes get emitted (vs. ~80 before) and pool_used never exceeds ~20.

## 5. Glyph mapping

Lout's word stream is a sequence of byte strings (`FULL_CHAR *`) with
implicit Latin-1 / Symbol / Dingbats encoding determined by the
font's LCM character map. Latin-1 bytes can be passed through to UTF-8
directly (the upper-128 path in `svg_emit_utf8`, z53.c:718), but byte
0x99 in a Symbol-encoded run is actually "trademark" and must map to
U+2122, not U+0099.

The path from a byte to a Unicode codepoint is:

1. `FontMapping(fnum, &fpos(x))` -> a `MAPPING` index for this font.
   (Lout's existing service; defined in `z37.c`.)
2. `MapTable[m]` -> a `MAP_VEC` whose `vector[byte]` is the
   PostScript / Adobe glyph name as an OBJECT word
   (e.g. `{trademark}` or `{aacute}`). Driven by the `.LCM` files in
   `lout/maps/`:
   - `lout/maps/LtLatin1.LCM` -- standard Latin-1 alphabet (~190 names).
   - `lout/maps/Symb.LCM`     -- the Symbol font's Greek-and-math layer.
   - `lout/maps/Dingbats.LCM` -- the ITC Zapf Dingbats glyphs.
3. `svg_glyph_to_unicode(name)` (z53.c:693) walks the
   `svg_glyph_table[]` array at z53.c:258-692 -- ~430 `(name, U+xxxx)`
   pairs -- and returns the codepoint, or 0 if not found.
4. `svg_emit_utf8(cp)` (z53.c:718) emits a 1-to-4-byte UTF-8 sequence
   with XML escaping for the seven reserved ASCII characters.

If no LCM mapping is available, or the glyph name isn't in the table,
the fallback is direct Latin-1-to-UTF-8 (z53.c:818). For ASCII text in
Times-Roman this never triggers the lookup -- the LCM exists but the
glyph names ("A", "B", ...) are well-covered in the front of the
table. For Symbol-font equations and Dingbats characters the table is
the entire path.

The current table covers all glyphs the User's Guide actually uses but
**not** the entire Adobe Glyph List. Closing the Symbol coverage gap
is a parallel work item being addressed by the agent that owns z53.c
font-side improvements; it appends to `svg_glyph_table[]` and to the
LCM files in lock-step.

`svg_emit_word_text` (z53.c:784) is the entry point and short enough
to read in one pass:

```c
for( p = s; *p != '\0'; p++ ) {
  c = (unsigned int) *p;
  cp = 0;
  if( mv != NULL ) {
    name_obj = mv->vector[c];
    if( name_obj != NULL && is_word(type(name_obj)) ) {
      gname = string(name_obj);
      if( gname != NULL )
        cp = svg_glyph_to_unicode((const char *) gname);
    }
  }
  if( cp == 0 ) cp = c;     /* Latin-1 fallback */
  svg_emit_utf8(cp);
}
```

## 6. Texture patterns

Lout's `coltex` library defines eight named textures: `striped`,
`grid`, `dotted`, `chessboard`, `brickwork`, `honeycomb`, `triangular`,
`string`. PostScript renders them via `LoutMakeTexture` /
`LoutSetTexture`, which receive a paint procedure and pattern.

z53.c emits one SVG `<pattern>` per named texture into a `<defs>`
block at the top of every page (`svg_emit_pattern_defs`, z53.c:1860).
The defs are emitted **before** the page-level Y-flip group so the
`patternUnits="userSpaceOnUse"` tile sizes are in non-flipped points.

Identification of the active texture happens in
`svg_tex_identify` (z53.c:1778): when `LoutMakeTexture` runs, its
paint-procedure body arrives as an `SVG_VK_PROC` value. The scanner
`svg_tex_scan_walk` (z53.c:1748) walks the proc and counts
distinctive operator names (`arc`, `setdash`, `findfont`, `show`,
`rlineto`, ...) into a `svg_tex_scan` struct. The result is matched
against signatures to choose one of `SVG_TEX_STRIPED` ... `SVG_TEX_STRING`.

On fill, `svg_ps_emit_path` checks `gs[gs_top].texture_kind`: solid
emits a literal `fill="rgb(...)"`, anything else emits
`fill="url(#lout-tex-NAME)"` referencing the pattern in defs. The
pattern's `currentColor` directive picks up the surrounding text/fill
colour, so coloured textures work without re-emitting the pattern.

## 7. @Graphic dispatch

`SVG_PrintGraphicObject` (z53.c:5219) gets a Lout ACAT (a tree of
WORD / QWORD / GAP_OBJ nodes). It first flattens the tree into one
flat byte buffer via `svg_graphic_concat` (z53.c:1136), preserving
GAP_OBJ as a space so the tokeniser can find operator boundaries.

Then **the leading non-whitespace character drives the route**:

- If it's `'<'`, the buffer is raw HTML/SVG markup. Pass through
  verbatim with `fputs(buf, out_fp)`. This is the path used by
  `@SVG { ... }`, `@SVGFile { ... }`, and the `@Math` / `@DMath` /
  `@ABC` macros from svgmacros (they all emit `<foreignObject>...`).
  Handled at z53.c:5239-5244.
- Otherwise, the buffer is treated as PostScript and handed to the
  embedded interpreter via `svg_ps_run` (z53.c:5272).

The PS interpreter then tokenises, parses, and executes -- possibly
hitting the `svg_run_cache` (z53.c:4992) which memoises the
parsed-token-array keyed on FNV-1a of the buffer bytes. Cache hits
skip both `svg_ps_tokenise` and `svg_parse_tokens`; misses parse and
insert.

When the interpreter can't fully evaluate the buffer (unknown
operator, ran past max recursion, stop without stopped), the
remaining tokens are dropped on the floor and the warning counter at
z53.c:4925 ticks up. The output is whatever drawing operators were
emitted **before** the failure; there is no rollback. Up to eight
"unknown PostScript operator '...'" warnings go to stderr, then
"further unknown PostScript operators suppressed".

When the buffer contains nothing executable at all (e.g. an entirely
unrecognised prologue), the output is just an XML comment naming the
unsupported construct -- this is the fallback path.

## 8. charpath bounding-box approximation

`coltex` and several @Graph prologue procs use the
`<string> false charpath flattenpath pathbbox` idiom to get the
bounding box of a rendered string. A faithful implementation would
need to parse the Type 1 / OpenType outline for every active glyph;
z53.c approximates instead.

`SVG_OP_CHARPATH` (case at z53.c:3622) lays down one axis-aligned
bounding-box rectangle per character of the input string. The
per-character advance is `font_size * 0.5` (the same fixed-pitch
fudge used by `svg_ps_show` at z53.c:2957 and `SVG_OP_STRINGWIDTH` at
z53.c:3609); ascent and descent are `font_size * 0.8` and
`font_size * 0.2`. Five `moveto`/`lineto`/`closepath` calls per
character close out a clean rectangle subpath, and `cur_x` is
advanced past the string so `pathbbox` (when it runs next) reads
back a plausible total width.

This is enough for every charpath consumer in `coltex` and the
@Graph axis labelling code, both of which only need the bbox
extents, not the actual outline. Real glyph outlines are
out-of-scope for this back end and the limitation is documented in
[`lout/NEXT_OPTIMIZATIONS.md`](../lout/NEXT_OPTIMIZATIONS.md).

`flattenpath` and `pathbbox` themselves are stubs that consume their
operands and push reasonable approximations from the path
accumulator -- look in `svg_ps_exec_op` for the case bodies.

## 9. Cross-references

The link callbacks (`LinkSource`, `LinkDest`, `LinkURL`) emit
`<a xlink:href>` overlays sized to the supplied bounding box. The
exact emission shapes:

- `LinkSource(name, llx, lly, urx, ury)` -> `<a xlink:href="#ID">`
  wrapping a `pointer-events="all"` `<rect>` of the given size. The
  ID is generated by `svg_emit_link_id` from the symbol name with all
  non-alphanumeric characters replaced by `_` and an `LOUT` prefix.
- `LinkDest(name, llx, lly, urx, ury)` -> `<a id="ID">` wrapping a
  zero-size `<rect>` at `(llx, ury)`. Zero-size because the anchor is
  for scrolling and search; the visible content is the surrounding
  page material, not the rect.
- `LinkURL(url, llx, lly, urx, ury)` -> `<a xlink:href="URL"
  target="_blank">` wrapping a sized rect. URL is XML-escaped by
  `svg_emit_xml_escaped` (z53.c:760).

These are the SVG/HTML analogues of the PDF `/Dest` and `/URI`
actions that z49.c emits.

## 10. svgmacros

The macros at `lout/include/svgmacros` are deliberately thin Lout
definitions that dispatch on `@BackEnd`. Each one falls into one of
three paths depending on which back end is live:

| Macro      | SVG mode emits                                  | PS/PDF mode falls back to     |
|------------|-------------------------------------------------|-------------------------------|
| `@Math`    | `{ "<foreignObject>...math...</foreignObject>" } @Graphic {}` | `@Body` as plain words |
| `@DMath`   | as `@Math` but with `class="math math-display"` | `@Body` as plain words        |
| `@ABC`     | `{ "<foreignObject>...abc-music data-abc..." } @Graphic {}` | `"[ABC music notation:" @Body "]"` |
| `@SVG`     | `{ @Body } @Graphic {}` (raw markup passthrough) | `"[inline SVG omitted ...]"` placeholder |
| `@SVGFile` | `@IncludeGraphic @Path {}`                      | `"[SVG file ... omitted ...]"` placeholder |

The SVG-mode body always opens with `<`, which hits the
raw-passthrough path in `SVG_PrintGraphicObject` (section 7). The
foreignObject content is rendered client-side by KaTeX
(`class="math"`) or abcjs (`class="abc-music"`) once the resulting
HTML loads in a browser.

`@DMath` is the most recent addition (May 2026). It was added so the
KaTeX `displayMode: true` rendering path could be selected for display
math without an inline-vs-display heuristic at the JS layer; mdlout.py
emits `@DMath { ... }` for `$$...$$` and ` ```math ` fences, `@Math`
for `$...$` and `\(...\)`. The HTML's KaTeX bootstrap reads
`class="math-display"` vs. plain `class="math"` to choose `displayMode`.
Before `@DMath` existed mdlout.py was post-processing the HTML to
inject delimiters, which collided with KaTeX's auto-render heuristic
on edge-case content.

All five macros are opt-in via `@SysInclude { svgmacros }`. mdlout
injects that include automatically when any routed Markdown block is
present (see mdlout.py's `_generate_lout` for the trigger logic).

## 11. Performance

Wall-clock numbers below are for a single-pass build of
`doc/user/all` (the 327-page User's Guide), warm cache, `-O3`,
measured on the maintainer's WSL2 box. Numbers come from
`lout/SVG_PERFORMANCE.md` and the running notes in
`lout/NEXT_OPTIMIZATIONS.md`.

| Change                                      | Wall   | Notes |
|---------------------------------------------|--------|-------|
| Pre-optimisation baseline                   | ~77 s  | linear-scan dict, strcmp-chain op dispatch |
| + `svg_dict_lookup` FNV-1a + open addressing | ~38 s | -50% wall; biggest single win |
| + hoist `filledsquare/...` strcmp guard     | 36.2 s | 20-strcmp guard moved behind a first-char switch (`svg_is_graph_symbol_proc`, z53.c:4805); only `f/d/s/c/t/p` names pay the cost |
| + `setvbuf(out_fp, 128 KiB)`                | 36.5 s | system time -19%; wall flat because the previous fix dominated user-CPU |
| + memoise parsed @Graphic token streams (`svg_run_cache`) | 35.6 s | 256-entry ring buffer keyed on FNV-1a of the buffer; cache hits skip tokenise+parse entirely |
| + hashed `svg_ps_exec_op` dispatch (this round) | ~32 s | ~58% total reduction from the pre-opt baseline |

The dominant remaining cost (per `SVG_PERFORMANCE.md` section 4) is
the @Diag prologue's per-node dict thrash and the fact that
`svg_dict_stack_lookup` still walks every level. Further wins would
come from name interning (turn the strcmp at each level into a pointer
compare) and from `<text>` emission consolidation (fewer fprintf
calls per word). Both are tracked in `NEXT_OPTIMIZATIONS.md`.

Two micro-decisions worth flagging because they trip up new readers:

1. **`svg_outbuf[]` is module-static, not stack** (z53.c:107). `setvbuf`
   documents that the supplied buffer must outlive the stream; a stack
   buffer in `SVG_PrintInitialize` would be freed before
   `PrintAfterLastPage` flushes.
2. **The PS interpreter state `g_psstate` is module-persistent** across
   `PrintGraphicObject` calls (z53.c:1391). PS-internal translates
   emitted in a parent @Graphic (e.g. the arrowhead-position translate
   inside the @Diag prologue) must remain in effect when the child
   arrowhead @Graphic later runs.

## 12. Known limitations and further work

Three trackers, in order of granularity:

- [`lout/SVG_PORTING.md`](../lout/SVG_PORTING.md) -- function-by-function
  port plan from z49.c to z53.c. Living document; consult before adding
  or rewriting a callback. Includes per-issue postmortems for things
  like the thin-connector-stroke regression (section 4.5 above), the
  arrowhead-glyph dropouts, the clip-empty semantics around
  `ldiagdolinkdraw`, and the texture-pattern coverage notes.
- [`lout/NEXT_OPTIMIZATIONS.md`](../lout/NEXT_OPTIMIZATIONS.md) -- ranked
  list of remaining performance work, each item annotated with expected
  speedup and complexity.
- [`lout/SVG_PERFORMANCE.md`](../lout/SVG_PERFORMANCE.md) -- read-only
  performance audit: profile traces, hot paths, the wall-clock table
  above with its prior history.

This document deliberately does **not** duplicate those trackers. They
move; this orientation guide should not.

## 13. Testing

Three test surfaces, each driven by a top-level shell script in `tests/`:

### tests/snippets and tests/run_all.sh

`tests/snippets/*.lt` is a corpus of 53 single-feature Lout snippets --
plain text, headings, math, tables, @Diag arrows, @Graph plots,
underlines, mirror/scale/rotate, page chrome, raw SVG passthrough,
etc. The orchestrator `tests/run_all.sh` runs each snippet through
both back ends (PS and SVG), rasterises both to PNG (PS via
`ps2pdf | pdftoppm -r 150`, SVG via `rsvg-convert -d 150 -p 150`),
runs ImageMagick `compare -metric AE -fuzz 5%` for pixel-diff and
scikit-image `structural_similarity` for SSIM, and emits
`tests/report.html` -- a side-by-side gallery with per-snippet
verdict.

Current state: 53 Pass-Excellent, 0 Fail. Thresholds:
- text snippets: 5% pixel diff
- graphics-heavy snippets: 20% pixel diff

Any work on z53.c must keep this at 53/0.

### tests/user_guide_diff.sh

The big one. Builds the entire Lout User's Guide (`lout/doc/user/all`,
327 pages) through both back ends, rasterises every page at 100 dpi,
diffs page-by-page. Output is `tests/user_guide_diff/manifest.json`
plus the worst-10 side-by-side PNGs (`worst-01.png` ...
`worst-10.png`).

This is the test that catches whole-document regressions like the
thin-connector dropout (section 4.5). Methodology and current
aggregate stats are in `tests/user_guide_diff/README.md`.

### tests/browser_test.sh

Headless-Chrome verification of the JS-side rendering: KaTeX math
rendering inside `<foreignObject>`, abcjs music notation, hyperlink
behaviour. Runs `tests/browser_test.py` under headless Chromium
against `examples/*.html` produced by the SVG path; verifies the
expected DOM elements exist after JS has run. Catches things like a
broken KaTeX bootstrap (a syntax error in the inlined library, a
class-name change that no longer matches the `auto-render` selector,
or a missing `<script>` due to a `_build_html_scaffold` regression).

## Pointers back into the source

For the curious reader, the recommended entry points into z53.c:

- `lout/z53.c:5515` -- `svg_back` definition. Every callback name in
  the BACK_END struct is a hyperlink to the implementing function.
- `lout/z53.c:5219` -- `SVG_PrintGraphicObject`: the @Graphic
  dispatch.
- `lout/z53.c:3058` -- `svg_op_seed[]`: the canonical list of every
  recognised operator.
- `lout/z53.c:3213` -- `svg_ps_exec_op`: the giant switch that
  actually implements them.
- `lout/z53.c:1452` -- `svg_name_hash`: the FNV-1a function used by
  the dict, the op-table, and the run-cache.
- `lout/z53.c:1694` -- `svg_dict_gc_sweep`: the mark-and-sweep
  collector that keeps the dict pool bounded.

When in doubt, follow the line numbers from the BACK_END table in
section 2 of this document. The file is dense but structurally well
laid out; section comments mark the major regions.
