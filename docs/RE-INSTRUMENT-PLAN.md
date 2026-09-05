# Action Plan — Custom RPCS3 Instrumentation Build for RE

**Goal:** build a patched, config-driven RPCS3 that logs *which guest (PPC) code touches
a given piece of memory* — turning every remaining "which renderer draws this screen?"
and "what enforces this byte limit?" question into a repeatable three-step lookup. This is
the tool that unblocks the cosmetic/UX issues we could not crack from outside the emulator.

---

## 0. STATUS — built & validated (2026-07-14)

The tracer is **written and tested against the live RPCS3 source** (`49b0306`). Key
discovery: **RPCS3 already has memory breakpoints** (read/write/read-write) — they're
just compiled out behind the `HAS_MEMORY_BREAKPOINTS` CMake flag, and every guest load
already funnels through `ppu_feed_data` / every store through `vm::write*`, each with a
BP checkpoint. So we don't hand-hook opcodes — we **enable the built-in system and add a
tiny log-and-continue layer** at those two checkpoints. Far smaller and more robust.

**Everything is in `tools/og2_trace_patch/`:**
- `og2_trace.hpp` / `og2_trace.cpp` — the durable tracer (dedups by (type, guest-PC),
  logs `HIT`/PC/EA/value/LR/shallow-call-stack to `og2_trace.log`, flushes each line).
- `apply.py` — **one command** installs it into an RPCS3 source tree. Anchored on unique
  code strings (survives source drift), idempotent, self-verifying. Validated: 6 edits
  land, re-run is a no-op.
- `rpcs3_edits.reference.diff` — the exact 3-file diff, for review.
- `tools/trace_report.py` — digests `og2_trace.log` → `build/trace_reports/<name>.md`:
  reading PCs ranked by hit count, with call stacks, **auto-annotated against our known
  function map** (`KNOWN` list — extend as we learn).

**The whole loop (once RPCS3 is built):**
```
python tools/og2_trace_patch/apply.py <rpcs3-source-root>
cmake -B build -DCMAKE_BUILD_TYPE=Release -DHAS_MEMORY_BREAKPOINTS=ON && cmake --build build -j
# run YOUR build, PPU Decoder = Interpreter; find the address in the Memory Viewer;
# Debugger -> Add BP -> "Memory Read" at it; leave "Break on BPM" OFF; redraw the screen.
python tools/trace_report.py <rpcs3-dir>/og2_trace.log library-desc
# -> report ranks the renderer PCs; hand the top one to the disassembly step.
```
No config file, no opcode surgery — you drive it with the **normal debugger UI**, and it
logs instead of pausing. The only remaining cost is the one-time RPCS3 build (§4).

---

## 1. Why we need it (what's blocking us)

Every hard remaining problem is the same underlying question — *what guest code reads/writes
this memory, and with what values* — and we have no way to answer it with stock tooling:

- **RPCS3's debugger has execution-only breakpoints.** No data/memory (read/write) breakpoints,
  so we can't break on "the code that reads the library description string."
- **Cheat Engine can't see RPCS3's guest RAM.** The PS3 memory is a mapped/reserved region CE's
  scanner skips even with Writable off + mapped types on — so external memory-access tracing is out.
- **The library text renderer is unmapped.** Verified this session against the debugger (thread
  attached, valid results): the library description is drawn by NONE of the known text renderers.
  Every condense-divide site in the binary was breakpointed and none fired while the library was
  on screen:
  - `0x5A5124` / `0x59F25C` — desc-twin condense (`fdivs f26,f3,f13`, word `EF436824`)
  - `0x61D7D4` — `fdivs f26,f27,f5`
  - `0x5CD2D4` — menu condense (`fdivs f0,f1,f5`; do NOT clamp, it garbles UI)
  - `0xA1329C` / `0xA15868` — dialogue condense (`fdivs f26,f2,f1`)
  - `0x2A2A9C` — the shared per-glyph draw. Also silent → the library uses a separate text pipeline.

A hook *inside* RPCS3 sidesteps both walls at once: guest memory is a normal pointer there, so
we can log the guest program counter (`ppu.cia`) on any access we care about.

---

## 2. What it unlocks

- **Library description crush** (immediate) — watch the description string, get the reading PCs,
  identify the renderer, apply a K-advance / condense-clamp EBOOT cave (proven pattern below).
- **Unit-list name condensation** — the open [task #16] menu-renderer crush; watch the unit-name
  buffer, same fix pattern.
- **Status / stat / Spirit / Back Log screens** — every "some text is squished" screen becomes
  findable instead of guessed.
- **The JP byte-slot limit** — the big one. Watch the offset/length table the engine parses when
  it loads a description (reads) AND the buffer it copies text into (writes). That reveals whether
  the segment/line count is a field we can grow, or baked into code — i.e. whether we can splice
  BIGGER slots for `scr` scenario rows and library descriptions instead of shortening English to
  fit. (Today: `FixedData/*.dat` grow via `fixh_grow`; talk grows via LDBI `reinsert_grow`; but
  `scr` rows and library dict segments are fixed — see `docs`/memory.)
- A **screen → renderer → fit-params map** for the whole game, so remaining spacing/condense
  issues get fixed systematically rather than one reboot at a time.

---

## 3. The instrument — a config-driven memory-access tracer

Instead of hardcoding a target, the patch reads a small config file (`og2_trace.cfg`) from the
RPCS3 working dir **at emulation start**, so we retarget WITHOUT rebuilding. Format:

```
# type  start(hex)   end(hex)      one rule per line
R 30000000 31000000          # log guest reads whose EA is in [start,end)
W 30000000 31000000          # log guest writes in range
X 005A5124 005A5128          # log every EXECUTION of a PC in range (non-stopping)
```

On a matching access the hook logs, **deduped by (PC, type)** so it can't spew gigabytes:
`guest PC (cia) + effective address + value + a shallow call stack (a few return addresses
walked from r1)`. Output goes to a dedicated log channel / `RPCS3.log`.

**Hook location:** the PPU interpreter's load/store/branch handlers in
`rpcs3/Emu/Cell/PPUInterpreter.cpp` (e.g. the `LBZ` byte-load used to walk strings). Roughly:

```cpp
// inside the byte-load handler — fires when a renderer walks the string char-by-char
const u32 ea = (op.ra ? ppu.gpr[op.ra] : 0) + op.simm16;
if (og2_watch_read(ea)) {                       // og2_watch_* reads og2_trace.cfg
    og2_log_once(ppu.cia, ea, vm::read8(ea));   // dedup by (cia,type); include shallow stack
}
```

**HARD REQUIREMENT: run PPU Decoder = Interpreter** (Config → CPU). The LLVM/ASMJIT recompiler
inlines guest reads to host x86 and skips the C++ handler, so the hook stays silent. Interpreter
is slower but irrelevant for a few seconds on a menu screen.

Division of labor: **I write the patch** (config reader + interpreter hooks + dedup + shallow
call-stack, ~60–80 lines), tuned against your actual checked-out RPCS3 version. **You do the
one-time build**, then just edit `og2_trace.cfg` and read the log.

---

## 4. The build (the heavy, one-time part — your side)

1. `git clone --recursive https://github.com/RPCS3/rpcs3` (large; submodules incl. LLVM).
2. Windows toolchain: **Visual Studio 2022** (Desktop C++ workload), **Qt 6**, **Vulkan SDK**,
   **CMake**. Follow RPCS3's *Building on Windows* wiki.
3. Disk: budget ~15–20 GB for the bundled-LLVM build.
4. Drop in the patch, build **Release**. First build compiles LLVM → a few hours mostly
   unattended; rebuilds after a patch tweak are minutes.
5. Run *your* build; point it at the same game + config. All existing saves/config carry over.

**Cheap thing to try first (may skip the whole build):** the RPCS3 "Update Available" build —
if a newer release added **memory breakpoints** to the debugger (Add BP dropdown showing
Read/Write), we can set a read breakpoint on the string directly and skip building. Checked once
this session (not present); worth re-checking on each update.

---

## 5. The per-investigation loop (fast, repeatable — once built)

1. Boot to the target screen; leave it displayed.
2. Find the text/data in RAM with **RPCS3's own memory search** (works — it found the library
   string this session; note the guest address, e.g. `0x300cf7ba`).
3. Add its range to `og2_trace.cfg` (e.g. `R 300c0000 300d0000`).
4. Run in **Interpreter**, navigate to the screen, let it redraw.
5. Copy the `TRACE` lines (unique `cia` values) from the log; send them to me.
6. I disassemble around each `cia` (seg0: `foff = vaddr − 0x10000`; r2/TOC = `0xD5CAA8`), find
   the renderer's advance/condense/scale math, and build the fix.

---

## 6. Applying fixes (proven EBOOT pipeline — already in-repo)

Once a renderer is identified, the fix reuses the letter-spacing toolchain:

- `tools/build_eboot.py` + `build/eboot_code_patch.json` — rebuild the patched EBOOT byte-exact
  (K-advance caves, condense floor-clamps, etc.) from `_rollback/EBOOT.elf.orig`.
- `tools/patch_eboot_advance.py` / `patch_eboot_fitclamp.py` — red-zone-safe code-cave patterns
  (spill scratch to the stack red zone, scale/clamp, branch back). Every cave instruction is
  capstone-verified before wrapping.
- `tools/make_fself.py` — wrap the patched ELF into a fake-signed SELF RPCS3 boots.
- **Rollback:** `_rollback/EBOOT.BIN.orig` (pristine retail SELF). Always validate the built
  EBOOT by diffing against a clean baseline and disassembling the patched sites before deploy —
  the day-long crash saga was a poisoned-string overwrite, not the caves, so structural
  verification catches that class.

---

## 7. Phased milestones

- **Phase 0 — Baseline.** Clone + toolchain + build *unmodified* RPCS3, confirm it boots and runs
  the game. (De-risks the environment before any patching.)
- **Phase 1 — Instrument.** Add the `og2_trace.cfg` reader + interpreter read/write/exec hooks +
  dedup + shallow call stack. Rebuild.
- **Phase 2 — Prove the pipeline on the library.** Trace the description read → identify the
  renderer → build + deploy the condense/advance EBOOT patch → confirm the crush is gone.
  This validates the whole loop end-to-end.
- **Phase 3 — Sweep UX/UI.** Unit-list name crush (task #16), status/Spirit/Back Log screens, any
  other squished text. Build the screen→renderer map.
- **Phase 4 — Byte-slot growth.** Trace the scr/library offset-length table parser to determine
  whether we can splice bigger slots (removing the "shorten English to fit" compromise on
  objectives and library descriptions). **Concrete work-list already staged:**
  [`field_widening_skill_names.md`](field_widening_skill_names.md) — four owner-approved skill
  renames (Potential / Fortune / Double Attack / Telekinesis) blocked purely on byte-capped name
  fields, with exact offsets, slots, over-by counts, and collision notes. **As remote passes hit
  the byte wall on any string, append the item there** so this phase always has a verified,
  ready-to-apply target list instead of a hypothetical.

---

## 8. Risks & gotchas

- **Recompiler inlines reads** → hooks only fire in **Interpreter** mode. Non-negotiable.
- **Log volume** → dedup by `(cia, type)`; watch narrow ranges, not all of RAM.
- **Guest heap addresses shift per boot** → find the address fresh each session via RPCS3 memory
  search, then set the config range (a broad range like `R 300c0000 300d0000` survives reboots).
- **Build friction** is the main cost; everything after is fast. Budget the first build generously.
- **EBOOT edits are the one destructive step** → capstone-verify + baseline-diff every build;
  keep `_rollback/EBOOT.BIN.orig` handy. Never clamp the menu site `0x5CD2D4` (garbles all UI).
- **Cosmetic, not blocking** — the game is fully playable now. This effort is polish; scope it to
  appetite. Each phase is independently valuable and can stop at any point.

---

## 9. What each side does

| | Me | You |
|---|---|---|
| Tracer patch (config reader + hooks) | ✅ write, tuned to your checkout | — |
| Build environment + compile | guide | ✅ one-time |
| Per-investigation traces | tell you what to watch | ✅ run + paste log |
| Disassembly / renderer ID | ✅ | — |
| EBOOT fix + deploy | ✅ build + validate | reboot to test |

**Kickoff when ready:** start the `git clone --recursive` + toolchain install (the long-lead,
unattended part). Tell me your VS 2022 / disk status and I'll hand you the finalized patch +
tightened build steps against the current RPCS3 source.
