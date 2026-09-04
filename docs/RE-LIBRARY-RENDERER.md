# Library-description renderer — live trace findings (2026-07-14)

**How captured:** instrumented RPCS3 (local build `0.0.41-1-49b0306b`, PPU Decoder =
Interpreter, HAS_MEMORY_BREAKPOINTS + og2_trace) with a **Memory Read** BP on the
on-screen Valsion Kai-CF description text at guest `0x300e6d73` (found via Utilities ->
Memory Viewer -> string search "Valsion"). Redrawing the description tripped it;
`og2_trace.log` logged the reading instruction + call stack (log-and-continue, no pause).

## The hit
```
HIT R cia=0x0994AF8 ea=0x300E6D73 val=0x74('t') lr=0x082D538
  callstack: 0x82d538 > 0x82e418 > 0x27bb64 > 0x27d5f8 > 0x27dc84
```
This is a **different code path from the dialogue renderer (0xA123F0/0xA149E8)** — which
is exactly why the EBOOT letter-spacing K-patch never fixed the library crush.

## What each frame is (disassembled; foff = va - 0x10000)
- `0x994af8` — generic **strchr/byte-scan** helper (`lbz;extsb;cmpw;beq;addi`). Finds char
  `r4` in string `r3`. Low-level; not the fix site.
- `0x9b7530` — wrapper the callers use to invoke the scan.
- `0x82d510` — **length-to-delimiter** (`bl 0x9b7530; subf r3,r31,r3`) = strcspn-like.
- `0x82e418` (frame `0x82d538`'s caller) — the **text/markup PARSER**: scans the
  description for control bytes `';'(0x3b) '@'(0x40 linebreak) '<'(0x3c) '>'(0x3e term
  markers)`. Integer-only, no FP — this segments the text into lines; it does NOT apply
  the horizontal scale.
- `0x27bb64 / 0x27d5f8 / 0x27dc84` — orchestrators (call many subfns, no FP directly).
  `0x27d5f8`'s function calls: `0x2a478, 0x48138, 0x28250, 0x278da4, 0x27c7a8, 0x27b7a8,
  0x27ac40` — the **glyph DRAW (with condense scale)** is one of these siblings.

## Why the scale wasn't in the captured stack
The BP caught the **parser** reading the source text (it scans the whole string). The
**drawer** applies the condense (horizontal scale < 1 to fit English into the JP-width
box) and likely reads a **segmented/line copy** the parser produced, not `0x300e6d73`
directly — so it didn't hit this BP.

## Next step (focused follow-up)
1. Re-trace targeting the DRAWER: set a Memory Read BP on a byte in the **visible** first
   line ("A space-com...") — search that exact start string; the new (non-`0x994af8`) PC
   is the drawer.  OR trace writes to the glyph-quad/vertex buffer.
2. In the drawer, find the `fmul`/`fdiv` that computes X-advance * (boxWidth/textWidth).
   Clamp that scale to >= 1.0 (or disable auto-condense / widen the box) via an EBOOT
   code-cave patch, same mechanism as the dialogue letter-spacing fix
   (tools/patch_eboot_advance.py + make_fself.py). See [[font-advance-open]].

Trace artifacts: build/trace_reports/library-desc-valsion.md, og2_trace.log.

## Static follow-up (2026-07-14, same session)
- The parse/layout subtree (`0x82e338-0x82e900`, `0x27ac40`, `0x27b7a8`) is **integer-only
  — no FP**. So the condense is NOT a float scale in the layout; it's either integer
  advance math or applied in the glyph draw.
- The library draws text via **`0x6cfe54`** (a text-draw taking a float scale in f1),
  NOT the dialogue glyph-draw `0x2A2A9C` (subtree has zero `bl 0x2a2xxx`). Confirms
  separate path.
- `0x27c7a8`'s fn loads FIXED float scales from TOC (r2/TOC=0xD5CAA8) and passes them to
  `0x6cfe54`: `r2-0x355c = 1.0` (dup'd to f1+f2 = X+Y scale at 0x27d004), `r2-0x3534 =
  0.2`. These are per-element constants (name vs small text), **not** the computed
  overflow-condense.
- => The runtime-computed `boxW/textW` squish is still not isolated. Static reading has
  plateaued.

## Recommended next approach (fresh, focused)
Dynamic, not static: set an **execution** BP at `0x6cfe54` (the scaled text-draw), read
**f1** (the scale arg) on the call that draws the description — if f1 < 1.0 there, f1 IS
the condense scale; then back-trace where f1 is computed (the `fmul`/`fdiv` of boxW/textW)
and clamp it via EBOOT code-cave. Alternatively trace the measure pass (sum-of-advances)
that feeds the scale. Needs the live instrumented build (still set up).

## Full render tree mapped + static dead-end (2026-07-14)
Complete call tree of the description render:
`desc-layout fn (0x27bb..) -> parse 0x82e838 (0x82e418) -> multi-line DRAW LOOP 0x82c964
(repeats bl 0x82c378; bl 0x82c488 ~8x = 8 lines) -> per-line helpers (integer array
indexing, slwi) ; glyph cluster 0x29044c -> 0x290204/0x2917f0/0x291b5c/0x291c60`.
**Scanned ALL of it for scale ops: ZERO fmul/fdiv AND zero mullw/divw.** The library text
pipeline is entirely integer with no readable scale instruction — the condense is NOT a
plain arithmetic op in this tree. Likely candidates: (a) advance comes from a per-glyph
metrics table and the "narrow" look is a fixed narrow cell width (an integer constant/
table entry, changeable), or (b) the squish is a GPU/RSX-side sprite scale set in the
blit-setup (outside this integer tree). Fixed float scales found were per-element
constants (1.0, 0.2 via 0x6cfe54), not the overflow-condense.

## DEFINITIVE next step: enhance the tracer (not more static scans)
Static reading can't see runtime values. Add an **execution-trace mode** to og2_trace:
when guest PC == a configured address (or in a range), log the GPRs/FPRs. Point it at the
per-glyph draw (0x290204 region) or the draw-loop 0x82c964, rebuild (incremental, LLVM
cached ~10-15 min), re-run: it will dump the actual per-glyph advance / X positions and
the box-vs-line width, revealing exactly how the condense is stored so it can be patched.
This is the right tool; the memory-read BP only shows text reads, not the layout math.

## BATTLE NAMEPLATE centering — pinpointed (2026-07-22)
Repro: enemy battle nameplate clips its left ("Gaia" hidden behind portrait) with empty
space on the right = text positioned as if wider than drawn. Found via: memory-search the
name string -> 3 copies (source 0x30c519c6 stable across boots; display copies move each
boot); watch the text-draw entry 0x1f708, post-filter hits by the name pointer in a GPR.

**Draw path:** caller F @ 0x054200 computes a fixed box **anchor** from box coords
(`f1 = (r4[0x20]-r11[0xc]) + r7[0]`, e.g. 988) — NOT from text width — and calls the text
drawer **0x1f708** at 0x054258 (anchor in f1/f2, string ptr in r3).
Inside 0x1f708, the **per-glyph position** is:
```
0x1F978: f22 = lfs [r31+0xc]       ; horizontal SCALE (per-glyph struct field)
0x1F97C: f21 = lfs [r31+0x10]      ; vertical scale
0x1F980: fmadds f20, f31, f22, f19 ; glyphX = layoutOffset(f31=0x40(r28)) * scale(f22) + anchor(f19)
0x1F984: fmadds f17, f30, f21, f18 ; glyphY = 0x44(r28) * f21 + f18
0x1F988/8C: stfs f20/f17 -> 0/4(r30) ; write glyph screen pos
```
So each glyph's X = its layout-offset × scale + anchor. The clip means either the
layout-offsets (0x40(r28)) were summed at the WIDE advance (unpatched) while the draw is
narrow, or the scale f22 isn't compensating. **Need the runtime VALUES of f22 (scale),
f31 (layout-offset), f19 (anchor), f20 (result) for the name's glyphs to know which.**

**Blocker + fix in flight:** those are FP regs f14–f31, but the tracer logged only f0–f13.
Extended xhit to log all 32 FPRs (og2_trace.cpp `i<32`), rebuilding now. Next capture:
watch 0x1f978-0x1f990, filter the name's glyph run, read f22/f31/f19/f20 -> the exact fix.

### 2026-07-22 full-FPR capture — HYPOTHESIS OVERTURNED. 0x1f980 is NOT glyph advance.
Captured 40 clean hits/PC (full 32-FPR tracer confirmed live). At 0x1f980 for EVERY
element: **f31(off)=1.0, f22(scale)=0.0, f19(anchor)=X, and the result f20 == f19 exactly**
(read f20 fresh at the 0x1f988 store, since OG2_XTRACE logs regs BEFORE each instr). So
`f20 = 1.0*0.0 + anchor = anchor` — the fmadds is a **pass-through that places each element
at its anchor**; the "layoutOffset*scale" term is identically zero. 0x1f708 is a **generic
per-element 2D placer** (40 distinct r28 structs, one call each), NOT a per-glyph loop.
Rows 9–20 were a clean **2-column list** (X=478 then 890, Y stepping +34) = a menu. There
is no per-glyph horizontal advance at 0x1f980. The old "glyphX = layoutOffset×scale+anchor"
model is WRONG.

### The anchor IS the lever — right/bottom-aligned placement at 0x54200 (disassembled)
```
0x541a0: r3 = r4[0xc0]                 ; content struct A (-> r9, gets frame copied in)
0x541b4: r0 = r4[0xc4]; r11 = r0       ; BOUNDS struct (may be NULL)
0x54208: beq 0x542a4 if r0==0          ; no bounds -> skip alignment
0x5420c: f5 = r11[0x0c]                ; content WIDTH
0x54210: f3 = r11[0x10]                ; content HEIGHT
0x54214: f4 = r4[0x20]                 ; frame right-x
0x54218: f13= r4[0x24]                 ; frame bottom-y
0x5421c: f2  = f4 - f5                 ; right - width
0x54220: f31 = f13 - f3                ; bottom - height
0x54224/28: f1=r7[4], f0=r7[0]         ; base offset
0x5422c: f30 = f2 + r7[0]  = anchorX   ; = (frame.right - content.width) + base.x
0x54230: f10 = f31 + r7[4] = anchorY
0x54258: bl 0x1f708                    ; draw at (anchorX, anchorY)
```
So **anchorX = (frame.right − content.width) + base.x** — a RIGHT-aligned layout.
`r11 = r4->0xc4`, `content.width = r11[0x0c]`. If content.width is OVER-estimated for the
wider English name, anchorX slides LEFT → the name's start ("Gaia") goes behind the portrait
while the right end falls short of frame.right → **empty space on the right + left clip.
This exactly matches the user's screenshot.** The fix target is therefore the WIDTH value
`r4->0xc4->0x0c` (or the alignment itself), NOT a glyph-scale cave.

CAVEAT — path not yet live-confirmed for the NAME specifically: the 0x54200 linkage came
from a prior-session callstack note; this session watched only 0x1f708/0x1f978-90 (never
0x54200), and I did not identify which of the 40 elements was the enemy name. Before
patching, ONE capture must confirm the name goes through 0x54200 and read its actual
frame.right / content.width / base / anchor. Capture plan in the "NEXT CAPTURE" section below.

### 2026-07-22 (later) — 0x54200 CONFIRMED to be the WRONG path for the name. EXCLUDED.
Live capture of the 0x54200 anchor math (watch `0x1f708-0x1f71c,0x541fc-0x54260`) during a
fresh HUD draw, 40 elements. Read frame.right (f4@0x5421c), content.width (f5@0x5421c =
r11[0x0c]), base.x (f0@0x5422c): **content.width = 0.00 and base.x = 0.00 for ALL 40
elements**, so anchorX = frame.right exactly (707/318/890/478/640/314). This placer does
NOT use any text width — it positions UI *sprites/segments* (HP-bar pieces, the 2-column
478/890 stat list, portrait frames) at fixed frame corners. **The name string is NOT
positioned here.** So both 0x1f980 (scale=0 passthrough) AND 0x54200 (width=0 sprite anchor)
are dead ends for the name. The prior-session "nameplate = 0x1f708/0x54200" attribution was
wrong — that callstack was for a sprite element, not the name text.

**Correct model now:** the name TEXT is drawn by a separate glyph/text renderer that measures
the string and centers/right-aligns it (origin = center − measuredWidth/2, or right −
measuredWidth). English measures wider than the JP box expects → origin slides left → "Gai"
goes behind the portrait, dead space on the right. Same class as the library-desc renderer.

### THE RIGHT TOOL: memory-READ BP on the name string (full speed, like the library capture)
The memory-read BP path (og2::hit via HAS_MEMORY_BREAKPOINTS in ppu_feed_data) log-and-
continues WITHOUT forcing precise mode — full speed, no crawl. Procedure (this is how the
library renderer at 0x82e418/0x994af8 was found):
1. User navigates the game so the clipping name plate is about to draw (dialogue speaker
   plate, or hover an enemy in battle). NOTE: inputs are gamepad/XInput — only the USER can
   drive the game; Claude can only mouse-drive the RPCS3 GUI.
2. Memory Viewer (Utilities menu) -> String search the English name ("Sabers") -> address NP.
3. Debugger -> select main_thread (click combo, Down+Return) -> Add BP, "Memory Read", NP,
   leave "Break on BPM" OFF (log-and-continue).
4. User re-triggers the plate draw -> og2_trace.log gets `HIT R cia=<PC> ea=NP ... st=<stack>`.
   The reading PC + callstack = the name text measure/renderer.
5. foff = PC − 0x10000; disassemble; find the center/right-align width math; EBOOT-cave-patch
   (widen the box / clamp so origin can't go left of the portrait / left-align the name).

### 2026-07-22 UNIT-NAME-PLATE renderer FOUND via memory-read BP (full speed). Task #16.
Repro target: map-hover unit-info panel ("Canis" + pilot name "Gaia Sabers Soldier" squished
into the small plate = the horizontal-condense/compression class). Method that WORKED (proven,
no precise mode):
- Memory Viewer String-search "Sabers" -> 74 hits; the unit name "Gaia Sabers Soldier" has 2
  copies: 0x334c4ac0 (source) and 0x334cd350 (render/display copy). (addresses move per boot).
- Debugger: select PPU[0x1000000] main_thread -> Add BP -> Memory Read on BOTH -> log+continue.
- User re-hovered the enemy -> BP tripped on the DISPLAY copy:
```
HIT R cia=0x994d6c ea=0x334cd350 val=0x4761696120536162 ("Gaia Sab")
  callstack: 0x05152c > 0x0582d4 > 0x04554c > 0x061614 > 0x049c04   (leaf-first)
```
Call order root->leaf: **0x049c04 (panel renderer) -> 0x061614 -> 0x04554c -> 0x0582d4
(tag parser) -> 0x05152c/0x5147c (string copy) -> 0x994d6c (word-at-a-time copy leaf)**.
DISTINCT from library (0x82e418) and dialogue (0xA123F0) paths — this is its own renderer.

What each does (disassembled, foff = va−0x10000):
- 0x5147c: copies the display string into a 0x200-byte work buffer (memset via 0x9b6710, then
  0x9b6da0 -> 0x994d6c). Case-switch on r31[0x80] (string type -1/0/1/2/3).
- 0x0582d4: the TAG PARSER — `lbz 0x130(r1); cmpwi 0x3c('<')`, then checks 0x41('A')/0x4e('N')/
  0x55('U') — segments `<..>` control tags. Integer, no scale (same as library parser).
- 0x061614's fn: threads **f28-f31 (draw params: x, y, and scale factors)** through the stack
  (`lfs f28..f31, 0x11c/0x118/0x124/0x120(r1)` at 0x061520; TOC consts `lfs f1,-0x74c8(r2)` /
  `f2,-0x74c4(r2)` at 0x061774). **KEY: this renderer draws text with FLOAT scale params** —
  unlike the pure-integer library pipeline, so a scale-clamp cave patch is viable here.
- 0x049c04: panel-renderer root; f28-f31 scale/pos originate here or above (passed down).

**NEXT (to the fix):** find where the condense SCALE in f28-f31 is computed — trace up from
0x049c04, or exec-watch 0x061500-0x061780 + read f28-f31 at runtime to get the actual scale
value (e.g. 0.7) and whether it's boxW/textW-derived. Then either clamp that scale to a floor,
or widen the plate's box width, via an EBOOT code-cave (same mechanism as the dialogue
letter-spacing K-patch). BPs left set on 0x334c4ac0/0x334cd350 (harmless: og2::hit dedups by
(type,PC), so no log spam; re-hover won't re-log 0x994d6c until the log/seen-set is reset).
NOTE: the map-panel COMPRESSION and the dialogue-speaker-plate CLIP ("a Sabers Soldier") may be
different renderers — this capture was the map panel; the dialogue plate needs its own BP if it
turns out to differ.

### f28-f31 draw params at 0x061614 = IDENTITY (0,0,1.0,1.0) — condense not a float scale here
Exec-watched 0x061520-0x061544 (the f28-f31 param loads), user re-hovered, 40 hits at 0x61538,
ALL identical: **f28=0, f29=0, f30=1.0, f31=1.0** (xoff,yoff,xscale,yscale = identity). So the
0x061614-level draw applies NO scale. The visible squish is therefore either (a) applied in the
glyph-draw sub-function deeper than this chain (computes its own boxW/textW scale), or (b)
integer per-glyph advance / RSX sprite-fit — the SAME pattern that walled the library renderer.
Caveat: 40-cap may have dropped the actual long-name draw (panel has many text elems hitting
0x61538); a memory-BP-correlated capture (only the name element) would disambiguate.

### 2026-07-22 CONDENSE OP FOUND (static dig) — it IS a clean float scale. FIX SITE: 0x05812c.
Traced the draw nest down: **0x0614d8 (layout, threads f28-f31=pos+scale, loops segs) ->
0x45424 (seg draw, loops sub-segs) -> 0x57fb0 (glyph-quad SIZER)**. 0x57fb0 is called from
exactly 4 sites, all inside 0x45424 — it is THE sizer for this pipeline. Inside 0x57fb0:
```
0x0580a8  fmuls f13, f3, f12      ; f13 = base_scale * elem.width   (base_scale = the threaded
0x0580ac  fmuls f1,  f2, f11      ;   f28-f31 param = 1.0 identity, confirmed live)
0x0580c4  stfs  f13, 0x84(r1)     ; stash scaledW
0x0580c8  stfs  f1,  0x88(r1)     ; stash scaledH
...
0x058108  lwz   r9, 0xc8(r31)     ; r9 = elem[0xc8] = OPTIONAL scale-struct ptr (r31=element)
0x05810c  lfs   f12, 0x88(r1)     ; f12 = scaledH
0x058114  lfs   f13, 0x84(r1)     ; f13 = scaledW
0x058118/1c stfs f12/f13 -> 0x78/0x74(r1)   ; default: store unscaled (elem[0xc8]==0 path)
0x058120  beq   0x58140           ; elem[0xc8]==0 -> NORMAL text, no condense (skips)
0x058128  lfs   f9, 0x3c(r28)     ; f9 = elem[0xc8]->[0x3c]  === HORIZONTAL CONDENSE SCALE (<1)
0x05812c  fmuls f8, f13, f9       ; f8 = scaledW * condenseX
0x058130  stfs  f8, 0x74(r1)      ; overwrite with squished width  <<< THE SQUISH
0x058134  lfs   f7, 0x40(r28)     ; f7 = elem[0xc8]->[0x40] = vertical condense
0x058138  fmuls f6, f12, f7
0x05813c  stfs  f6, 0x78(r1)
```
**Mechanism:** normal (fitting) text has elem[0xc8]==NULL and renders unscaled. When a field's
text overflows its box, the layout attaches a scale-struct at elem[0xc8] with a sub-1.0 factor at
[+0x3c] (X) / [+0x40] (Y); 0x05812c applies it => the horizontal squish we see on "Gaia Sabers
Soldier". This is a CLEAN FLOAT scale (unlike library's integer/GPU) => **cave-patchable**.

**FIX (candidate):** code-cave divert at 0x058128 that floors f9 (and f7) to a minimum K, i.e.
f9 = max(f9, K). K=1.0 => no condense (full width, may overflow the box); K~0.80-0.85 => gentle
condense, stays legible without full overflow. Reuse the existing EBOOT cave infra (build/
eboot_code_patch.json + tools/patch_eboot_advance.py pattern; caves at 0xc45xxx, float consts in
TOC/cave). Overwrite 0x058128 `lfs f9,0x3c(r28)` with `b cave`; cave = lfs f9,0x3c(r28); lfs
fK,K; fsub/fsel to max; b 0x05812c. (Do the f7 path too, or leave vertical alone.)
Guarded by elem[0xc8]!=0, so ONLY overflowing fields are touched — normal text unaffected.

**BEFORE patching, confirm with ONE capture** (worth it): mem-read BP already showed the name at
0x334cd350; set an exec-watch on 0x058124-0x058130 while re-hovering, read f9 (the actual squish,
e.g. 0.6) + r28 (=elem[0xc8]) — confirms this fires for the name and gives a sensible K floor.
Also worth checking: does this same 0x57fb0 path serve the library/parts descriptions? If yes,
one clamp fixes the whole compression class. (The earlier "library = integer, unpatchable"
conclusion only scanned the library's own subtree, NOT 0x57fb0 — revisit.)

### 2026-07-22 CONFIRMATION CAPTURE at 0x05812c — operands re-identified; picture is nuanced.
Exec-watched 0x058124-0x05813c on a re-hover. CORRECTED operand roles: **f13 = the scale-ish
factor, f9 = elem[0xc8]->[0x3c] = a WIDTH/ref (not the scale)**; f8 = f13*f9. The unit panel
draws 8 sub-elements (r31 = 0x33685230 + i*0x100, i=0..7), same set each redraw:
```
 elem r31        f13      f9     f8     r25(text ptr)   note
 0  ..5230     0.1000   155.0    15.5    -              sub-1 scale, ref-width 155
 1  ..5330     0.9733     1.0     0.97   -
 2  ..5430     0.5050   155.0    78.3    -              <- ~50% scale x 155 ref
 3  ..5530     0.4506     1.0     0.45   -
 4  ..5630    16.0000     1.0    16.0    0x334cd390     near NAME(0x334cd350) -> a name GLYPH
 5  ..5730    16.0000     1.0    16.0    0x334cd530     name glyph
 6  ..5830    28.0000     1.0    28.0    0x334cd6d0     name glyph
 7  ..5930    28.0000     1.0    28.0    0x334cd870     name glyph
```
KEY (unexpected): the elements whose r25 points into the NAME string (4-7) have **f13 = 16/28 =
full glyph WIDTHS, f9=1.0 — NOT squished at 0x05812c**. The sub-1 scales (0.505, 0.451, 0.1) are
on elems 0-3, which do NOT point at the name. So **0x05812c is NOT where the name glyphs get
squished** — they pass through at full width. The visible name squish is therefore applied
either (a) as a reduced per-glyph ADVANCE (pen-X step < glyph width => overlap/compression) set
elsewhere, or (b) a parent/container transform (elems 0-3 may be the name's container/background
carrying the 0.505 scale that the glyphs inherit via position, not via their own f13). This is
the SAME distributed/not-a-single-clamp shape the library hit.
**Verdict:** renderer + call tree + sizer FULLY mapped (task #16 located), but the condense is
NOT a single clampable fmul at the glyph level. Fastest resolver now = EMPIRICAL: build a test
cave that floors f13 at 0x05812c (K=0.85) OR forces elem-container scale >=K, deploy, and LOOK —
if the name widens, that site owns it; if not, the squish is in the advance/parent path. Reversible.
Alternatively bank the RE and fix the ~6 worst names data-side (shorten). BPs still set on the
name copies (harmless, dedup).

### 2026-07-22 DEFINITIVE: this render path applies NO scale condense — scale = 1.0 everywhere.
Traced the advance path (user choice). Full nest with the horizontal-transform register at each
level:
- **panel root 0x049a34**: loops children, hard-codes `lis r28,0x3f80` => stores **0x3f800000 =
  1.0f** at [0x70]/[0x74] and passes as the scale to EVERY child's 0x0614d8 call (0x049aa4).
- 0x0614d8 threads it as f28-f31 (measured live = identity 0,0,1,1).
- 0x45424 -> 0x57fb0 pass it through unchanged (stored at [0x418..0x424]).
- **0x53630 (glyph/quad builder)**: computes glyph screen pos via `fmadds f3, f27, f25, f1` /
  `fmadds f4, f29, f24, f2` where f27/f29 = the horizontal/vertical transform = the threaded
  scale = **1.0**. So glyph positions use scale 1.0 => NO programmatic horizontal compression.
The sub-1 f13 values seen at 0x05812c were **HP/EN gauge fills** (fraction × 155px bar width),
NOT text. **CONCLUSION: the map unit-name plate renders at identity scale.** What reads as
"compression" is the natural tight advance of the small proportional panel font on a long name —
there is no runtime condense-scale to clamp here. Same practical outcome as the library (no
clean patch), but for a different reason (identity scale, not integer/GPU).

ONE unexplored branch for the truly-thorough: 0x053764 `fcmpu cr7,f30,const; blt 0x54088` — a
width-threshold test in 0x53630 that could route oversized text to a fit/condense path at
0x54088. Not chased (pattern strongly suggests more of the same). If ever revisited, disassemble
0x54088 and check whether it derives a boxW/textW scale.

## 2026-07-22 — LIBRARY DESC "big lines" DIAGNOSED (in-game repro), capture plan ready
The unit/pilot description "inconsistent sizing" = the renderer draws EACH of the JP fixed
line-slots at a font size tied to the SLOT (short-cap slots render enlarged). Confirmed live:
R-1 entry — the enlarged lines ("TYPE-1." Built for close-quarters combat," / " into a") map
EXACTLY to that entry's SHORT-cap segments (cap 42 / cap 21), while cap-81 slots render normal.
So font size ∝ f(slot width/cap), baked into the JP slot structure — NOT our English text, and
NOT the wrapper (the DP wrapper fixed the separate blank-line bug; this is orthogonal). Static
is a known dead-end here (the 1.0/0.2 TOC consts near 0x27cfe8/0x27d004 are name-vs-body element
scales, not the per-line pick). Also verified: descriptions reveal LINE-BY-LINE (○ advances), so
a "one line + rest blank" pilot entry is NOT truncation — our data had all lines w/ correct NULs.
**CAPTURE PLAN (memory-BP, full speed) to crack the per-line scale — READY TO RESUME:**
1. Instrumented build, R-1 unit library entry with the big lines, GUI arranged so the Memory
   Viewer search box is reachable (this was the blocker 2026-07-22 — the debug windows came back
   tangled after a GD reinstall; open a FRESH Utilities->Memory Viewer and position it visibly).
2. String-search a BIG-line word ("Built") AND a NORMAL-line word ("mobility") -> 2 addresses.
3. Debugger main_thread -> Memory-Read BP on both -> re-open/scroll the R-1 desc so both redraw.
4. Compare the two HIT call stacks: if the big line goes through a different draw/scale than the
   normal line, that diff is the mechanism. Then exec-watch that draw, read the scale per line
   (expect big-line scale > normal), find where it's set from the slot width, and clamp it.
Repro is 100% reliable (short slot ALWAYS enlarges) — strongest position yet to crack this renderer.

### 2026-07-2x — MECHANISM CONFIRMED from the display buffer (memory read, no BP needed)
Found the R-1 desc display buffer at guest 0x300e6dc1 (4 copies: +0x1a0/0x260/0x380; source at
0x30c7xxxx). Read its bytes directly in the Memory Viewer. Structure: each display LINE = the
slot's [english][space-pad-to-cap], and lines are joined by **`@` (0x40)** separators — e.g.
`..."REAL PERSONAL TROOPER"      @TYPE-1." Built for close-quarters combat, @it has high mobility
and attack power.   @It inherits...`. **There is NO per-line size control byte** — only text,
spaces, and `@`. So the enlargement is purely: **font scale = boxWidth / (chars up to the next
`@`)**. Long/space-padded lines (wide-cap slots) => normal; short lines (short-cap slots:
"TYPE-1." Built…combat," cap~42, " into a" cap~21) => proportionally BIGGER. This is baked into
the JP slot caps; our wrapper fills+pads to cap but can't change the cap (position-addressed NUL).
**=> The clean fix is a RENDERER scale-clamp** (cap the boxW/lineLen scale at some max so short
lines can't blow up). The exact scale instruction still needs the live capture — the memory-read
BP on 0x300e6dc1 is STAGED (set 2026-07-2x) but wouldn't trip because the description won't
REDRAW while the debug windows hold focus (game/controller needs the game window focused). FINISH:
focus the game window, back out + re-open R-1 so it redraws through the big line -> BP HIT gives
the draw callstack -> exec-watch that draw, read the scale for a big vs normal line -> clamp.
Data-side is NOT clean: renderer likely trims trailing spaces (so extra padding won't shrink the
font), and caps can't grow without moving NULs. Renderer clamp is the path.

### 2026-07-2x — STATIC hunt for the scale (GUI-free); found the scale constants + candidates
The desc draws scaled text via **0x6cfe54** (takes scale in f1, saved f31 at 0x6cfe68 — so the
per-line scale is chosen by the CALLER, not inside 0x6cfe54). Scale constants (TOC=0xD5CAA8):
**0.2 = TOC-0x3534, referenced EXACTLY ONCE @ 0x27cfe8** (desc BODY text draw) — desc-specific.
**1.0 = TOC-0x355c, 6 refs, ALL in 0x279xxx-0x27dxxx** (library renderer; names/titles + 0x27d004).
The desc renderer is a **control-code STATE MACHINE @ 0x27ca00-0x27d034** (0x27c7a8 recurses into
itself for nested/sized spans at 0x27ce80); body=0.2, "big" segments take a larger scale chosen
inside this machine — NOT one clean clampable instruction. fdivs candidates found: cluster
0x82945c/47c/49c (generic const-a/b transform, prob not it), 0x6cfd9c (interp in the fn BEFORE
0x6cfe54), 0x82a6e0, 0x82ac44 — none confirmed as the boxW/lineLen justify. UNRESOLVED statically.

### THE REAL BLOCKER + the tool to fix it next time
The live capture (read f1 at 0x6cfe54, or memory-read BP on the desc buffer, to see big-vs-normal
scale) is the definitive answer but is blocked by RPCS3's **debug-window GUI being unreliable to
drive via screenshots** (overlay/game Z-order makes clicks slip — Add-BP never registered, 0 hits;
user identified this). **FIX = enhance the tracer with a FILE-DRIVEN memory-read BP** (write target
guest addr to e.g. og2_membp.txt; hook og2::hit to also fire for addresses in that file) so the
capture needs ZERO Debugger/Memory-Viewer clicking — mirrors og2_xwatch.txt for exec. ~15-min
incremental tracer rebuild (apply.py + rebuild). Then: write the desc buffer addr, user redraws
R-1, read the HIT callstack -> the draw fn -> exec-watch it -> read f1 per line -> clamp. This
removes the only thing that's actually stopping us. Everything else (mechanism, constants, state
machine location) is already mapped above.

### 2026-07-2x — EMPIRICAL TEST: 0x27cc5c (the 1.0 draw in the desc loop) RULED OUT
Found all 6 bl-0x6cfe54 sites in the desc renderer: **five @ scale 1.0** (0x2798ac/0x27a80c/
0x27a91c/0x27aa20 in the title area, + 0x27cc5c inside the body loop) and **the body @ 0.2
(0x27cff4)**. Hypothesis: the big lines route through the 1.0 site 0x27cc5c. TEST: flipped its
scale load 0x27cc4c from 1.0(-0x355c) to 0.2(-0x3534) [2-byte patch], rebuilt+deployed, rebooted.
**RESULT: big lines STILL big (fully-visible R-1 screenshot) => 0x27cc5c is NOT the enlarged-line
draw.** Reverted. CONCLUSION: the enlargement happens on the **0.2 BODY draw itself (0x27cff4)** —
i.e. 0x6cfe54 JUSTIFIES/stretches short lines up. 0x6cfe54 is a thin wrapper -> calls 0x79755c,
0x6cf438, **0x6cfdec** (the fn holding the divide **0x6cfd9c: f6=f8/f11; then interp
f3=(f10-f6)*f12 + f6*f7**), 0x7974bc. **0x6cfd9c is the prime justification-scale candidate** —
if f11=text-width and f8=box-width, f6=box/text = the stretch. CLAMP f6<=1 (or a max) to stop
short lines enlarging. NEEDS runtime confirm (read f6/f8/f11 per line) which is STILL blocked:
the PPU won't re-render the desc on demand (it draws once, GPU repeats; Change-Unit / re-select
don't reach the game / don't rebuild under our control), and the exec-watch fired 0 times (log
never grew => desc-render code not executing). **This is the hard blocker: no reliable desc
RE-RENDER trigger for a PPU capture.** Next-session fixes (pick one): (a) file-driven memory-read
BP in the tracer (no GUI); (b) a tracer hook that logs f-regs at 0x6cfd9c on the NEXT N executions
after a flag file is touched, so we don't need precise-mode nav; (c) hook the desc-open path so
opening ANY unit reliably re-renders. Then read f6 big-vs-normal, clamp, done. Mechanism + exact
candidate (0x6cfd9c) are nailed; only the runtime-confirm + clamp remain.

**RECOMMENDATION (name compression):** bank this RE (renderer fully mapped + proven scale-
identity). For readability, the productive levers are elsewhere: (1) the dialogue-speaker-plate
CLIP is a POSITIONING bug (anchor/right-align), a separate and likely-simpler target; (2) data-
side shorten the ~6 worst-overflowing display names (reversible). The map-panel name is likely
acceptable as-is (natural rendering, not a scaled squish).

### NEXT CAPTURE (single grind closes it)
1. Boot instrumented, reach the clipping enemy nameplate, PAUSE.
2. Memory Viewer -> string-search the enemy name (e.g. "Gaia") -> note the display-copy
   guest addr NP (moves each boot).
3. Set og2_xwatch.txt = `0x1f708-0x1f71c,0x541fc-0x54260` (entry gives r3=string ptr;
   anchor math gives r4,r11,r7 + computed f30/f10). Clear-then-immediately-rearm to blow
   past the blue-screen load (precise mode stalls it).
4. Re-render the plate. In og2_trace.log: find the 0x1f708 hit with r3==NP (that's the name
   draw), read back its 0x54200 frame: r4[0x20]=frame.right, r11=r4->0xc4, r11[0x0c]=width,
   r7[0]=base, f30=anchorX. Compare width vs (frame.right - desired-left) to see the
   over-estimate, then patch: clamp content.width, or convert this widget to left-align, or
   fix the width MEASURE (writer of r4->0xc4->0x0c). Prefer clamping/measure-fix over a
   blanket left-align (0x54200 is generic — HP numbers etc. legitimately right-align).

**Capture logistics learned:** precise mode chokes the battle-load transition (blue
screen). Trick (user's): clear og2_xwatch.txt to blow past the load at full speed, then
re-arm right as the battle animation starts so precise mode only covers the nameplate
render. Also: display-copy addresses change every boot — re-search each session; code
addresses (0x1f708 etc.) are stable.

## LIVE RUNTIME DATA captured (2026-07-15, tracer v2 working)
Exec-register logger WORKS. Key fix: RPCS3's interpreter is threaded (block tail-calls),
so the watch must force **precise mode** (OG2_XPRECISE -> next_fn=&ppu_ret, one instr per
loop) at the real dispatch loop `PPUThread.cpp:2411` (`fn->fn(*this,...)`). The earlier
hook sites were recompiler-fallback/savestate paths, never run in Interpreter mode.
Set the watch via env `OG2_XWATCH="lo-hi,..."` before launch (makes the whole emu slow).

Watched 0x82c964-0x82cb00 + 0x27bb50-0x27bbb0 on a Grungust description (11 lines):
- **Draw context r3 = 0x329fe4e0**; the **11 line-descriptors are at ctx+0x1248**
  (0x329FF728), **stride 0x48 (72 bytes)**. Loop var `r26` = line index 0..10.
- **Descriptor layout** (from accessors): `+0x04` = array of 4-byte **segment entries**;
  `+0x44` = **segment count** for the line (0x82c36c: `lwz r3,0x44(r3)`; 0x82c378:
  `add r3,r3,idx*4; lwz r3,4(r3)`). ~16 segments/line max.
- Per line: `0x82c36c(desc)` -> seg count, then unrolled loop `0x82c378(desc,i)` (fetch
  seg) + **`0x82c488(...)` (DRAW seg)**; `r26++`, `r21 += 0x48` (next line desc).
- FP regs throughout = **1280 / 720** (render-target dims), held constant — **NO
  fractional condense scale**. The squish is INTEGER, in the glyph X-advance inside
  `0x82c488`'s subtree (one level below the watched range).

## Concrete next step (one more trace, then patch)
Re-trace with a wider watch `OG2_XWATCH="0x82c378-0x82c530,0x82c964-0x82cc80"` and also
read the per-line descriptor bytes (Memory Viewer @ 0x329FF728, 72B) to get: each line's
**X start** (for the centering-offset fix), **width/clip** (for the long-line fix), and
the **per-glyph advance** in 0x82c488 (for the compression fix). Those three values are
exactly the three goals.

CAUTION from mining the existing dump: the layout fn 0x27bb40 does `lwz r22,0x88(r1);
cmplwi r22,0xf; ble` = a std::string SSO length check, so the value **1207 seen in
r22/r23/r30 is most likely the description's total CHAR COUNT, not a pixel box-width** —
do not patch it as a width. Other candidates (r29=1146, r12=1008, r11=141) are set before
the captured window; their roles are unconfirmed. Get real pixel dims from the deeper
trace (0x82c488 subtree) / descriptor bytes, not from these. NOTE: changing OG2_XWATCH needs a relaunch+reboot (env parsed at
startup) — a future tracer tweak to re-read the watch from a file at runtime would make
iterating far faster (no slow reboot per watch change).

---

# 2026-07-27 SESSION — MAJOR CORRECTION + mechanism identified (live-confirmed)

## ⚠️ 0x6cfe54 IS AN AUDIO VOLUME FADER, NOT A TEXT DRAW. Strike lines 51-57 and 388-407.
Three sessions of RE were aimed at the sound mixer. Disassembly + live capture both prove it:
- `0x6cfdec` writes `chan->duration` / `chan->target` / `chan->start`; `0x6cfd9c`'s
  `fdivs f6,f8,f11` = `elapsed/duration` (a fade LERP), **not** boxW/textW.
- Caller `0x5977b0` does `fmuls f1,f1,0.01f` on a u16 in 0..100 = **volume slider percent**.
- LIVE CAPTURE corroboration (this session, watching 0x6cfe54 at full speed): the "scales" were
  `f1=1 f2=24`, `f2=128`, `f1=-101`, `f1=102`, `f1=-310`, `f2=-1`. Those are **fade frame-counts
  and volume levels**, not font scales. f2=24 = a 24-frame fade.
- => `0x27ca00-0x27d034` is the library page's **pad-input / scroll / voice-playback** handler.
  `0x27cff4` (0.2 over 15 frames) DUCKS BGM before a voice clip. `0x27d010 mulli r10,r22,0x2710`
  builds `cueId = bank*10000 + index`.
- => The old "0x27cc5c empirical test FAILED" is now EXPLAINED, not inconclusive: it flipped a
  BGM un-duck level. Also `tools/patch_eboot_fitclamp.py` (SITES 0xA1329C/0xA15868/0x5CD2D4)
  has always pointed at the wrong instruction (0xA1329C is `f26 = 1.0/f1`, a reciprocal, and is
  flag-gated by `lbz r0,0xd4(r31)` / `beq 0xa13294`).

## THE MECHANISM IS INVERTED FROM THE OLD HYPOTHESIS: the engine only SHRINKS, never enlarges.
Both auto-fit guards are one-directional (`bgt` on measured>maxWidth; `blt cr1`). There is no
`boxWidth/charCount` justification instruction anywhere — which is why nobody could find one.
**The "big" lines are the UNMODIFIED BASELINE. The "normal" lines are LONG lines that got
CONDENSED.** This matches the in-game repro exactly (cap-81 slots overflow -> squeezed;
cap-21/42 slots fit -> untouched).

## LIVE-CONFIRMED THIS SESSION (full-speed exec-watch, input alive)
- **The library DOES render through `0xa123f0`** — 40 hits, `r3=0x30068b10`, via `lr=0x5ce18c`.
  (The old "library never touches 0xa1xxxx" conclusion was WRONG; it reaches it through a
  DEFERRED render pass, which is why memory-BPs on the source string only ever caught the parser.)
- `0xa149e4` (the twin) + its shrink target `0xa16ea8` **fire** (40 hits). `0xa13a2c` (primary
  twin's shrink) gets **0 hits** — the TWIN is the active one for this screen.
- `0xa16ea8` shrink is ONE constant element: `measured=1749.6  maxW=672  ratio=0.3841` — NOT
  per-line, so the per-line differential is NOT this outer shrink.
- **`0x5cb970` = SetFontSize(obj, xSize=f1, ySize=f2)**; writes `stfs f1,0x2c(r3)` /
  `stfs f2,0x30(r3)`. Harvested 960 samples. x/y ratios are **EXACT POWERS OF 0.9**:
  `1.0, 0.9, 0.81, 0.729, 0.6561`. So the engine steps size down by x0.9 until the line fits.
- **DESC path = `lr=0x82f08c`, obj `0x30068b10`, `y=24` CONSTANT, x in {21.6, 19.44, 17.496,
  15.7464}** = 24*0.9^n for n=1..4. **Only the HORIZONTAL is condensed; height is fixed.**
  Widest:narrowest = 24/15.7464 = **1.52x**, which matches the screenshot.
- The size ladder is NOT a table: 19.44 / 17.496 / 15.7464 occur **ZERO** times in the binary
  (21.6 occurs once, at 0xd6212c). Computed at runtime. The 0.9 constant EXISTS in TOC-adjacent
  data (0xd55514, 0xd60750, 0xd60844, 0xd61cb8, 0xd63cc4) but **no `lfs fX,disp(r2)` loads it**
  => it is loaded via a non-r2 base (a style/config struct), not a TOC constant.

## OPEN — where exactly the per-line size is chosen (next session starts HERE)
`0x82f04c fmr f1,f23 / 0x82f050 fmr f2,f24 / ... / 0x82f088 bl 0x5cb970` is the desc's
SetFontSize call. `f23` is loaded at `0x82edb8 lfs f23,0x2c(r19)` (r19 = a style/line
descriptor; the synthesis found per-line descriptors at `ctx+0x1248 + idx*0x48`, stride 0x48,
matching a prior live capture of 11 line descriptors at 0x329FF728).
**BUT (measured this session): with `0x82ec8c` entered 40x, `0x82edb8` and `0x82ee14` get ZERO
hits** — the active path branches around them, so `0x82f088`'s block is NOT reached from the
`lfs f23` I attributed to it (different basic block / probably a different function). DO NOT
patch 0x82edb8 on the assumption it feeds 0x82f088 — that was disproven before patching.
NEXT: find the real writer of `obj[0x2c]` for the desc. Best probe = watch the **entry of the
function that contains 0x82f088** (find its prologue by scanning back for `mflr`/`stdu r1`),
plus `0x5cb970`, and correlate `r3` == desc obj. A memory-read BP (og2_membp.txt) on
`descObj+0x2c` would also catch every reader at full speed.

## TOOLING WIN (this is what unblocked everything)
`OG2_XPRECISE` is now DECOUPLED from watch-active (og2_trace.hpp `g_xprecise`, set only when
og2_xwatch.txt contains the token `precise`). A watch on a FUNCTION-ENTRY / BRANCH-TARGET PC now
runs at **FULL SPEED with gamepad input alive** — the exact blocker that killed 2026-07-22.
Also: **re-writing og2_xwatch.txt RESETS the per-PC 40-hit cap**, so cycling the file content
(alternate a trailing space) harvests unlimited samples with no user action and no rebuild.

## 2026-07-27 (cont.) — ROOT CAUSE FOUND. It was never the renderer. TWO of our own bugs.

### BUG 1: our own fontsize cave was COMPOUNDING (eboot_code_patch.json #23/#24/#25)
`patch_eboot_test_fontsize.py` redirects `stfs f1,0x2c(r3)` @0x5cb984 (SetFontSize) into a
cave @0xc45c80 that does `f1 *= Kf`. Its design note assumed *"fontsize is written ONCE per
string"*. **FALSE** — the engine repeatedly RE-APPLIES an element's existing size (captured
live at 0x82edc0 AND 0x82f088, plus the render pass at 0x5cec**/0x5d2***). Every re-apply
multiplied by Kf AGAIN => geometric decay `24 -> 21.6 -> 19.44 -> 17.496 -> 15.7464`
(Kf=0.9; the constant at 0xc45cb0 is `3f666666`=0.9, the "0.8" in the note is STALE).
Depth varied per element by render history, so sizes looked RANDOM, not length-driven.
FIX (tools/patch_eboot_fontsize_once.py): first tried an equality test vs obj[0x2c] — worked
for 0x82edc4 but other paths passed non-bit-identical values and decay reached **0.9^9**.
Final: **HARD FLOOR relative to Y**, `x = max(x*Kf, y*Kf)` via fsel. Square input (x==y, the
normal font case) => x = y*Kf on EVERY call; re-apply of y*Kf => max(y*Kf^2, y*Kf) = y*Kf, a
fixed point. Idempotent BY CONSTRUCTION, no path can evade it. Non-square callers
(0x058468 passes 1280x1 etc — this setter is also used for non-font objects) keep x*Kf.
Cave safety re-verified vs the unpatched EBOOT: f0 dead until 0x5cb9b8, f13 dead until
0x5cb9a4, f12 LIVE (do not touch), no CR field read anywhere in the fn, no stack writes
(leaf uses the red zone at -0x10(r1) — the round-2 Library crash lesson).

### BUG 2 (the big one): WE SPACE-PAD EVERY LINE AND THE RENDERER MEASURES THE PADDING
`fix_dictionaries.py` wrote `[prefix][english][SPACE PAD to cap][NUL@orig]`. Verified on the
deployed data: **10/10 slots padded, `strlen == cap` every time** (e.g. cap=81 visible=48
trailing=33; cap=21 visible=6 trailing=15). The renderer measures the whole NUL-terminated
string, so:
```
measured = 1749.6px = 81 glyphs x 21.6      <- 81 = the BYTE CAP, not the text
maxWidth =  672px   = ~31 glyphs
ratio    = 672/1749.6 = 0.384                <- crushed to 38% => unreadable
```
A cap-81 slot ALWAYS measured 81 glyphs regardless of content; a cap-21 slot measured 21,
fit, and rendered full size. **That is why apparent font size tracked the SLOT CAP instead
of the text**, and why it looked like a renderer/justification bug for three sessions.
It also DISPROVES the old note claiming "the renderer likely trims trailing spaces".
FIX: NUL-fill instead of space-pad (one line in fix_dictionaries.py) => measured width is
the ACTUAL text width; real lengths cluster at 48-54 so lines become near-uniform.
`d[off+cap]` is outside the written slice so the original terminator is preserved.

### ORDER MATTERED
Bug 1 masked Bug 2: while sizes decayed randomly there was no length correlation to see.
Fixing Bug 1 turned the symptom into a CLEAN length correlation (short lines big, long lines
small) — which is what exposed Bug 2. Bug 1's fix looked like "no change" in-game but was
the step that made Bug 2 visible.

### DEPLOY GOTCHA (cost a corrupted-GD cycle)
`deploy.py` `gd_root` pointed ONLY at `../dev_hdd0/game/BLJS10133` (the RETAIL tree, which
doesn't exist here). The **instrumented** build has its OWN `dev_hdd0`, so it kept a stale
Logic.psarc.sdat (26,563,680 vs the new 26,562,992) and `cellGameDataCheck` failed with
"game data corrupted". FIXED: `_wipe_gd()` now iterates `CFG["gd_roots"]` (both trees) and
prints each wipe. See [[ingame-test-procedure]].

### BUG 3 (2026-07-27, after fixes 1+2): FIT-MODE letter-spread — the fit-test measures at K=1.0
After un-padding, lines rendered at ONE size but with per-line letter-SPACING differences
(some spread to the margin, some compact). Live per-line capture at the twin guard 0xa14ca8:
`maxW=672` always; `measured = n * 21.6` EXACTLY (1080=50*21.6, 712.8=33*21.6, 648=30*21.6,
453.6=21*21.6, 388.8=18*21.6) => the fit-test MEASURE is FLAT MONOSPACE at K=1.0, while the
DRAW uses our advance K=0.57 (patch_eboot_advance.py). So a 33-char line "overflows" 672 on
paper (712.8) and enters FIT-MODE, when it draws to 406px and fits easily.
FIT-MODE (0xa16ea8 twin / 0xa13a2c primary) = the JP equal-distribution justify: sets a flag
(`stw r16=1,0x114(r1)` @0xa16ee8), scales glyphs by ratio=maxW/measured, and DISTRIBUTES them
across the box on a path that ignores K -> those lines land at exactly boxW/n per glyph
(spread), while "fitting" lines draw compact at K. On screen: fits-path 12.3 game px/char
(=21.6*0.57 exactly), fit-mode 20.4 px/char for ratio .943 (=21.6*.943, no K). Screenshot
scale for this UI = 1.716 screenshot px per game px (box 1165px = 679 game px ~ maxW 672).
FIX (tools/patch_eboot_fit_kaware.py, deployed): both engines' `fcmpu` (0xa126d0 cr6 /
0xa14ca4 cr1) redirected to caves @0xc45cc0/0xc45cf0 that compare (measured*K) vs maxW,
K read from the SAME constant as the advance caves (0xc45950) so they can't drift.
COMPARISON ONLY -- do NOT scale f1 itself: fit-mode's ratio (fdivs f27,f12,f1) distributes
at K=1.0, so a K-scaled f1 would make genuinely-overlong lines overfill ~2x.
Caves spill r12/-8(r1) + f13/-0x10(r1) (red-zone pattern of the 14 advance caves).

### BUG 4: right-edge CLIPPING at WRAP=54 -> WRAP=50
With fit-mode no longer rescuing them, 50-54 char lines (47% of lines at WRAP=54) that draw
past 672 (proportional glyphs vs the flat estimate: 54*12.3=665, +wide glyphs -> >672) CLIP
at the box edge ("nearly every entry has cut-off text"). Measured trade: WRAP 54->0 entries
lose tail, 51->4, 50->6, 49->11, 48->19. WRAP=50 keeps every line <=~660px even at +7% wide
=> no clip, no fit-mode; 6/363 (all short PILOT bios: P_0x001CA9, P_0x001EDA, P_0x002B23,
P_0x002C58, P_0x002CE3, P_0x009095) drop a trailing sentence -> hand-tighten later.

### STACK SUMMARY (all four were needed, in this order, each masking the next):
1 fontsize cave compounding (EBOOT floor) -> 2 space-padding measured (NUL-fill) ->
3 fit-test at K=1.0 (K-aware fcmpu caves) -> 4 WRAP=54 clipping (WRAP=50).
Deploy state 2026-07-27: EBOOT.BIN (30 regions incl. #23-25 floor + 4 fit caves) and
Logic.psarc.sdat (NUL-fill, WRAP=50). deploy.py now wipes BOTH GD trees (gd_roots).

### 2026-07-27 (later) — data/wrapping pass after the renderer was clean
- **';' is a LINE-BREAK control byte in the library parser** (0x82e418 scans @ < > ;). In-game:
  'damaging it; it limped back' rendered as 'it' / ' it limped back' (phantom break + leading
  space). 117/363 dict + 20/64 keyword entries had ';'. FIX: `desemicolon()` in
  fix_keyworddata.py, called unconditionally from `strip_terms()` (shared by dict + keyword
  fixers): '; x' -> '. X'. NEVER emit a raw ';' into library-parsed text.
- **Tiny-slot orphans** (JP sentence-tail slots, writable cap 6-9; 56 total, 17 cap-6, 14 cap-9):
  wrap_slots now (a) rewards a sentence END in a tiny slot, (b) may SKIP a tiny slot only right
  after a sentence end (renders as a paragraph gap; never blank mid-sentence), (c) penalizes a
  mid-sentence orphan (ORPHAN=250; SKIP=20 so 'Hiryu / Kai.' -> 'Hiryu Kai.' + gap).
- **PRE-EXISTING BUG in the sentence-end test**: `t[-2:-1] in ".!?"` is TRUE for every 1-char
  token ("" is in any string) -> 'a'/'A'/'I' counted as sentence ends and were REWARDED into
  tail slots ('bit of a', 'A'). Now `re.search(r'[.!?]["\')\]]?$', t)`.
- Orphans 13 -> 0 after rules + 7 hand rewordings in build/dict_desc_en.json (U_0x002D7A,
  U_0x004CA5 [dropped 'PTX-007-02' model no.], U_0x00E122, U_0x01313C, U_0x0146F7, P_0x004CE0,
  P_0x0062EB). 'Hiryuu' -> 'Hiryu' (canonical per UnitData.dat). Gown -> Gaun in WeaponData.
- Still open (other archives): 'Gown' x2 in Battle/040.bmd; scenario-select instruction line
  clipped at left (General2d windowdataMain.wtd); AbilityElementData '|'/'?' markers (A/B).
- 2026-07-27 (final pass): 6 short pilot bios (P_0x001CA9, P_0x001EDA, P_0x002B23, P_0x002C58,
  P_0x002CE3, P_0x009095) hand-reworded to fit their slot shapes at WRAP=50 -> dictionaries now
  0 truncations / 0 orphans / 0 semicolons. Other archives: Gaun x2 in Battle/040.bmd;
  scenario-select line shortened 70->56 chars in General2d windowdataMain.wtd (was left-clipped;
  repacked via wtd_tool apply -> repack_override -> encrypt_sdat wrap, HMAC verified);
  AbilityElementData: dropped the ￤/￢ marker flattenings ('|'/'?') from all 20 filter labels
  (option A) + Ctr->Counter, Evd->Evade. (Option B - restore the fullwidth chars - is possible if
  the JP glyphs turn out to be meaningful icons; the font cell lookup for U+FFE4/U+FFE2 was NOT
  resolved: the master-table indexing is not cp>>11/(cp>>8)&7/cp&0xff — revisit if needed.)

### 2026-07-27 (library-wide pass) — TWO MORE structural bugs, all three library files
Symptom: entries starting mid-word ('ge strategic transport plane' <- 'Large'; 'riz Raven') and a
FOREIGN line from the next entry appearing at the end of an entry.
- **Slot-0 HEADER: every entry's first line = [1-3 byte control header][U+3000 indent][text].**
  Kinds seen: `08 01 58`, `13 04 29`, `04 03 9d` (3B), `06 de` (2B), `aa`/`ac`/`55`/`52` (1B), or none.
  dict_entries.json/keyword_entries.json recorded the prefix INCONSISTENTLY (168/363 dict +
  20/64 keyword entries had prefix=0 for a real header) -> we overwrote the header with the first
  letters of the EN text, and the renderer (which still skips the header length) ate them.
  FIX: prefix := len(bytes before the first e3 80 80 in slot 0), derived from work/ JP; verified
  427/427 entries; headers now preserved byte-for-byte (audit column 'hdr preserved').
- **EMPTY slots bleed into the next entry.** The line walker COLLAPSES NUL runs, so a fully-NUL
  slot (unused trailing slot, or a DP-skipped tiny slot) makes it read straight on into the next
  entry's slot 0 ('riz Raven adds a Tesla Drive booster pod'). Space-PADDING never had this
  problem (no slot was ever empty) - my NUL-fill introduced it. FIX: every slot holds >= 1 byte;
  an unused slot gets a single space (renders as a blank line, keeps slot count == JP).
- fix_keyworddata.py was STILL space-padding (measured-padding bug) -> now NUL-fill + non-empty,
  and it uses the shared slot-aware DP `wrap_slots` (moved into fix_keyworddata.py).
- DP: abbreviation periods (Integ./No./Mk./Dr./...) are NOT sentence ends (was rewarding breaks
  after them: 'Colony Integ. / Army', 'No. / 3 Hoffnung'). desemicolon: '; and|but|or' -> ', and'.
- 3 more keyword rewordings (Elpis x2, Antarctic Incident) for structural tiny-slot orphans.
FINAL AUDIT (tools: /tmp-style script, see [[library-text-rules]] memory): UnitDict 1308 slots,
PilotDict 795, KeyWord 628 -> headers preserved 100%, EMPTY 0, space-padded 0, ';' 0,
tiny orphans 0, dictionary truncations 0, keyword problems 0.

## 2026-07-27 — STATUS SCREENS pass (Unit/Pilot status, help popups, spirit menu)
### WTD (General2d) headers colliding — the WTD renderer draws ASCII at ~1.26 half-cells/char
Measured from screenshots: 'Twin Spirit/SP' (14 ch) overflowed a 16-cell column by ~10%. So the EN
budget for a WTD label = JP_cells / 1.26. Shortened by JP source text: 地形適応->Terrain,
強化パーツ->Parts, 特殊能力->Ability, 特殊スキル->Skills, ツイン精神／ＳＰ->Twin Spirit,
精神コマンド／ＳＰ->Spirit Command, 検索項目->Filter, 特殊スキル名->Skill Name, 地形適応【空】->
Adapt【Air】 (etc). Left alone: 'Stats' (能力, 4 cells; still ~1 char over), terrain 2-letter
labels Sk/Ln/Se/Sp (2 cells, tight but readable), and the 22 one-kanji spirit-status badges
(熱->Va, 魂->So ... = a legend row; 2-letter codes jam together; single letters would be ambiguous).

### HelpData / SpiritData / PartsData / ACEBonusData: MULTI-LINE text = fixed line strides
Screens: help popup 'ts the terrain best.' / 'mbat, and' (lines starting mid-word + bleeding into
the next entry); spirit effect 'l, Valor, Alert,'. ROOT CAUSE: the worksheet apply's
splice_grow resizes each string in place and shifts what follows, but these renderers locate
line k by a FIXED byte offset from the entry start:
  * HelpData: a tiny binary record precedes each entry: `00 03 | 00 2c | ...` = N=3 lines,
    W=0x2c=44 fullwidth chars -> line k starts at hdr + k*(44*3+1). Byte-exact match:
    our seg0 shrank 135->89, line 2 read at +136 = 45 bytes into seg1 ('ts the terrain best.'),
    line 3 at +269 ran into the NEXT entry ('mbat, and').
  * SpiritData/PartsData/ACEBonusData: seg0's 1-byte header IS ITS LENGTH ('F'=0x46=70 for a
    70-byte segment, 'L'=76, '1'=49, '@'=64, '.'=46, 0x1c=28) -> line 2 at start+len+1. The
    translators had faithfully kept the header CHAR in the EN ('FHit rate 100%...').
FIX: tools/fix_fixh_text.py — full OFFSET-PRESERVING rebuild from JP for all four files:
walk the STRI block, group text segments between binary separators into entries, preserve the
1-3 byte header byte-for-byte (strip the header char the extractor baked into the EN), join
the entry's EN (worksheet by seg offset + helpdesc_inline_en.json by JP body), wrap over the
exact JP slots with the slot-aware DP (HelpData display cap 92 = 44-fullwidth box at K=0.57
+ <=7% fit-mode condense; Spirit 48; Parts 46; ACEBonus = 1:1 'lines' mode since each segment is
an independent bonus), NUL-fill, never empty; SOFS-referenced singles that outgrow their slot
(spirit names 'Intuition') are appended+repointed via fixh_grow (nothing moves). Replaces
fix_helpdesc.py in deploy.py. Overrides: build/<stem>_en_override.json.
Result: HelpData 752 entries (221 multi) 0 lost after a 60-entry verified rewrite pass
(build/helpdata_en_override.json, agents self-verified with scratchpad/help_verify.py);
Spirit 88 (12 multi, 10 names grown) 0 lost; Parts 87 (28 multi; 28 clean overrides replacing
the old 'Move +1, Mobility +5 / as well.' fragment joins) 0 lost; ACEBonus 173 (62 multi) 0 lost.

### Pilot NAMEPLATE crush (unit status screen, 'Gaia Sabers Soldier')
Not fixed. Real display names >= 15 chars are few (Gaia Sabers Soldier 19, Union Army Soldier
18 [sic: シュテドニアス軍兵 = Shutedonias soldier — inconsistent with the pilot bio], Mass-Prod.
M-Children 21, Volkruss (Combined) 19, Kerberion Present 17...); the same name renders fine on
the Pilot tab. Data-side shortening of the generic mook names is the cheap path; the panel
renderer (0x049c04 chain, 'identity scale') was a dead-end RE earlier.

## 2026-09-01 — "Game data is corrupted" on the retail RPCS3: fresh install impossible there
The top-folder "retail" RPCS3 is v0.0.41-19638 (folder name stale); instrumented is v0.0.41-1.
Retail's `cellGameDataCheck` creates `/dev_hdd0/game/BLJS10133/USRDIR` during the check and reports
the data as existing (no "directory ... not found" line); the game then calls cellGameGetSizeKB on
an empty dir and shows "Game data is corrupted" 1 s after cellGameContentPermit, copying nothing.
The instrumented build logs "not found" -> the game takes cellGameCreateGameData -> installs.
=> deploy.py no longer wipes GD; `_sync_gd()` mirrors the deployed archive into every gd_root,
creating a complete GD from build/gd_template (PARAM.SFO + ICON0.PNG captured from a real
install) + all five disc-folder sdats (sizes must match exactly). `--wipe` keeps the old path.

## 2026-09-03 SkillData descriptions: a TWO-LINE RECORD format (not plain strings)
Pilot Training / Learn Skill showed line 1 crushed to ~1/3 size with a tiny line 2
("is performed."). Cause found by walking SOFS: 6 of the 43 skill descriptions are RECORDS,
not C strings. Their SOFS pointer targets

    [u16 A = tail CHARACTER count][u16 B = body bytes + 1][body][NUL][tail][NUL]

exact on all six in JP (Lucky A=11 B=160, Guts A=6 B=148, Combination A=32 B=142, Chance
A=7 B=148, Re-Attack A=5 B=139, Cont Action A=52 B=151). body = LINE 1, tail = LINE 2 of the
2-line box. A record is identifiable because the pointer target starts with a NUL byte.
The extractor only saw the tail, so the worksheet key is the TAIL offset and fix_skilldesc.py
patched the body by content search -- which poured ~110 English chars onto line 1 and 5 onto
line 2. Same class as the HelpData/Spirit fixed-stride bug: OUR per-JP-line pour, not a
renderer bug.
FIX tools/fix_skilldata.py (deploy.py apply, after fix_skilldesc): rebuilds each record
contiguously with honest A/B and splices, fixing every SOFS offset (splice_grow's model).
Text: build/skilldata_desc_en.json {"0x<key>": {"use":"two","two":[l1,l2]}}.
LINE BUDGET 54 ASCII chars (JP line 1 = 46-53 fullwidth). 19 of the 37 SINGLE descriptions
also exceeded it (up to 119 chars) and were rendering shrunk -> 17 shortened in the worksheet,
2 kept as CANARIES converted to records (Counter 0x000AB7, Support Atk 0x000972) to test
whether the game recognises a record purely by the leading NUL. If the canaries render as two
clean lines, the other long ones can be restored to full 2-line text; if they render blank,
records are gated on something else and the shortened singles stay.
