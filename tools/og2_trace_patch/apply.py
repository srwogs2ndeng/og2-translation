#!/usr/bin/env python3
"""apply.py - install the OG2 memory-access tracer into an RPCS3 source tree.

One command. Anchored on unique code strings (not line numbers), so it keeps working
as RPCS3 evolves, and it's idempotent (safe to re-run). It:
  1. copies og2_trace.hpp / og2_trace.cpp into rpcs3/Emu/Cell/
  2. adds the tracer include + call at the READ checkpoint (ppu_feed_data)
  3. adds it at the two WRITE checkpoints (vm::write8 / vm::write<T>)
  4. registers og2_trace.cpp in Emu/CMakeLists.txt
Then build with memory breakpoints ON (prints the exact commands).

    python tools/og2_trace_patch/apply.py <path-to-rpcs3-source-root>
"""
import os, shutil, sys

HERE = os.path.dirname(os.path.abspath(__file__))


def edit(path, anchor, insert, tag, count=1):
    """Insert `insert` right after `anchor`. `count` occurrences (0 = all)."""
    s = open(path, encoding="utf-8").read()
    if tag in s:
        print(f"  = already patched: {os.path.basename(path)}"); return True
    if anchor not in s:
        print(f"  !! anchor NOT found in {os.path.basename(path)} -- source changed; patch by hand:\n     {anchor[:70]}"); return False
    s = s.replace(anchor, anchor + insert, count if count else -1)
    open(path, "w", encoding="utf-8", newline="\n").write(s)
    print(f"  + patched: {os.path.basename(path)}"); return True


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    root = os.path.abspath(sys.argv[1])
    cell = os.path.join(root, "rpcs3", "Emu", "Cell")
    if not os.path.isdir(cell):
        sys.exit(f"!! not an rpcs3 source root (no rpcs3/Emu/Cell): {root}")
    ok = True

    # 1. drop in the tracer sources
    for fn in ("og2_trace.hpp", "og2_trace.cpp"):
        shutil.copy2(os.path.join(HERE, fn), os.path.join(cell, fn))
        print(f"  + copied {fn} -> rpcs3/Emu/Cell/")

    # 2. READ checkpoint: PPUInterpreter.cpp
    ppui = os.path.join(cell, "PPUInterpreter.cpp")
    ok &= edit(ppui, '#include "util/sysinfo.hpp"',
               '\n#include "og2_trace.hpp"  // OG2 tracer', "og2_trace.hpp")
    ok &= edit(ppui,
               'debugbp_log.success("BPMR: breakpoint reading 0x%x at 0x%x", value, addr);',
               '\n\t\tOG2_TRACE(\'R\', static_cast<u32>(addr), value, ppu);',
               "OG2_TRACE('R'")
    # 2a. FILE-DRIVEN memory-read BP w/ FULL register dump: fires for EVERY guest read (not
    #     just debugger-registered BPs) when og2_membp.txt is non-empty. Runs at full speed
    #     (no precise mode) so game input still works -> lets us capture a renderer's registers
    #     as it reads a known buffer, with NO debugger/memory-viewer clicking. Insert right
    #     after the existing HasBreakpoint block, still inside the ifdef.
    ok &= edit(ppui,
               "OG2_TRACE('R', static_cast<u32>(addr), value, ppu);\n\t\tppubreak(ppu);\n\t}",
               "\n\tOG2_MEMBP('R', static_cast<u32>(addr), ppu);",
               "OG2_MEMBP('R'")

    # 2b. EXECUTION register-logger hook: PPUThread.cpp interpreter dispatch. Insert
    #     OG2_XTRACE(ppu) after every `const u32 op = vm::read32(ppu.cia);` (all 3
    #     interpreter dispatch sites) so a PC in OG2_XWATCH dumps its register state.
    #     Gated by g_xactive (false unless OG2_XWATCH set) -> ~free when unused.
    ppt = os.path.join(cell, "PPUThread.cpp")
    ok &= edit(ppt, '#include "stdafx.h"',
               '\n#include "og2_trace.hpp"  // OG2 exec tracer', "og2_trace.hpp")
    ps = open(ppt, encoding="utf-8").read()
    if "OG2_XTRACE(ppu)" in ps:
        print(f"  = already patched (exec): {os.path.basename(ppt)}")
    elif "const u32 op = vm::read32(ppu.cia);" not in ps:
        print("  !! exec anchor not found in PPUThread.cpp -- patch by hand"); ok = False
    else:
        ps = ps.replace("const u32 op = vm::read32(ppu.cia);",
                        "const u32 op = vm::read32(ppu.cia); OG2_XTRACE(ppu);")
        open(ppt, "w", encoding="utf-8", newline="\n").write(ps)
        print(f"  + patched (exec): {os.path.basename(ppt)}")
    # 2c. THE important one: the threaded-interpreter main loop. In Interpreter mode a
    #     block runs via tail-calls (next_fn = fn+1), so mid-block PCs never re-enter the
    #     loop -> a plain per-loop check misses them. When a watch is active, force precise
    #     mode (next_fn = &ppu_ret => one instruction per loop) and trace every PC.
    ps = open(ppt, encoding="utf-8").read()
    MAIN_OLD = "fn->fn(*this, {*op}, op, state ? &ppu_ret : fn + 1);"
    NO_POLL  = ("OG2_XTRACE(*this); fn->fn(*this, {*op}, op, "
                "(state || OG2_XPRECISE) ? &ppu_ret : fn + 1);")
    MAIN_NEW = ("OG2_XPOLL(); OG2_XTRACE(*this); fn->fn(*this, {*op}, op, "
                "(state || OG2_XPRECISE) ? &ppu_ret : fn + 1);")
    if "OG2_XPOLL()" in ps:
        print("  = already patched (main loop): PPUThread.cpp")
    elif NO_POLL in ps:  # upgrade an earlier patch that lacked the live-reload poll
        open(ppt, "w", encoding="utf-8", newline="\n").write(ps.replace(NO_POLL, MAIN_NEW))
        print("  + upgraded (main loop, added XPOLL live-reload): PPUThread.cpp")
    elif MAIN_OLD in ps:
        open(ppt, "w", encoding="utf-8", newline="\n").write(ps.replace(MAIN_OLD, MAIN_NEW))
        print("  + patched (main interp loop): PPUThread.cpp")
    else:
        print("  !! main-loop anchor 'fn->fn(*this,...state ? &ppu_ret : fn+1)' not found"); ok = False

    # 3. WRITE checkpoints: vm.h  (both write8 + write<T> end with 'ppubreak(*ppu);'
    #    and both have addr+value in scope; prepend the trace call before each).
    vmh = os.path.join(root, "rpcs3", "Emu", "Memory", "vm.h")
    ok &= edit(vmh, '#include "rpcs3qt/breakpoint_handler.h"',
               '\n#include "Emu/Cell/og2_trace.hpp"  // OG2 tracer', "Emu/Cell/og2_trace.hpp")
    vs = open(vmh, encoding="utf-8").read()
    if "OG2_TRACE('W'" in vs:
        print(f"  = already patched (writes): {os.path.basename(vmh)}")
    elif "ppubreak(*ppu);" not in vs:
        print("  !! write anchor 'ppubreak(*ppu);' not found -- patch by hand"); ok = False
    else:
        vs = vs.replace("ppubreak(*ppu);",
                        "OG2_TRACE('W', addr, value, *ppu); ppubreak(*ppu);")
        open(vmh, "w", encoding="utf-8", newline="\n").write(vs)
        print(f"  + patched (writes): {os.path.basename(vmh)}")

    # 3c. FILE-DRIVEN memory-WRITE BP with full register dump. Mirrors OG2_MEMBP for reads so
    #     og2_membp.txt also fires on WRITES (logged as type 'W'). Essential for "who SETS this
    #     field?" questions -- a read BP only ever shows the consumers, never the producer.
    #     Inserted AFTER the debugger-gated HasBreakpoint block (so it needs no debugger BP),
    #     guarded by `if (ppu)` since ppu is null for non-guest writes. Two indent levels:
    #     write8 closes at 2 tabs, the write<T> template at 3.
    vs3 = open(vmh, encoding="utf-8").read()
    if "OG2_MEMBP('W'" in vs3:
        print("  = already patched (membp writes): vm.h")
    elif "OG2_TRACE('W', addr, value, *ppu); ppubreak(*ppu);" not in vs3:
        print("  !! membp-write anchor not found in vm.h -- patch by hand"); ok = False
    else:
        for tabs in ("\t\t\t", "\t\t"):   # deepest first so the shallow pattern can't shadow it
            anchor = "OG2_TRACE('W', addr, value, *ppu); ppubreak(*ppu);\n" + tabs + "}"
            vs3 = vs3.replace(anchor, anchor + "\n" + tabs + "if (ppu) OG2_MEMBP('W', addr, *ppu);")
        open(vmh, "w", encoding="utf-8", newline="\n").write(vs3)
        print("  + patched (membp writes): vm.h")

    # 3b. fmt fix (needed to LINK with -DHAS_MEMORY_BREAKPOINTS=ON): vm::write<T>'s BPMW
    #     debug log formats the written `value`, but T can be a struct with no
    #     fmt_class_string specialization (cellGcmSys does vm::write<CellGcmContextData>),
    #     giving an unresolved-external at the final link. Drop the value from that log.
    vs2 = open(vmh, encoding="utf-8").read()
    OLD_FMT = '"BPMW: breakpoint writing(%d) 0x%x at 0x%x",'
    if OLD_FMT in vs2:
        vs2 = vs2.replace(OLD_FMT, '"BPMW: breakpoint writing(%d) at 0x%x",')
        vs2 = vs2.replace("sizeof(dest_t) * CHAR_BIT, value, addr);",
                          "sizeof(dest_t) * CHAR_BIT, addr);")
        open(vmh, "w", encoding="utf-8", newline="\n").write(vs2)
        print("  + patched: vm.h (BPMW log drops un-formattable struct value)")
    else:
        print("  = already patched: vm.h BPMW log")

    # 4. register og2_trace.cpp in the Emu build
    cml = os.path.join(root, "rpcs3", "Emu", "CMakeLists.txt")
    ok &= edit(cml, 'target_sources(rpcs3_emu PRIVATE',
               '\n\tCell/og2_trace.cpp', "Cell/og2_trace.cpp")

    # 5. build-enablement fix (needed to build at all on MSVC/Ninja with bundled zlib):
    #    RPCS3's FindZLIB.cmake points ZLIB::ZLIB's IMPORTED_LOCATION at
    #    'libzlibstatic.a' -- a filename no toolchain emits. The real bundled target
    #    (zlibstatic) outputs zs.lib on WIN32 (suffix "s") / libz.a elsewhere, so the
    #    link dies with "missing and no known rule to make it". Repoint at the real
    #    file (kept IMPORTED so libpng/curl try_compile checks still resolve it).
    fz = os.path.join(root, "buildfiles", "cmake", "FindZLIB.cmake")
    BROKEN = ('    add_library(ZLIB::ZLIB STATIC IMPORTED)\n'
              '    set_target_properties(ZLIB::ZLIB PROPERTIES\n'
              '        IMPORTED_LOCATION "${CMAKE_BINARY_DIR}/3rdparty/zlib/zlib/libzlibstatic.a"')
    FIXED = ('    if(WIN32)\n        set(_og2_zlib_file "zs.lib")\n'
             '    else()\n        set(_og2_zlib_file "libz.a")\n    endif()\n'
             '    add_library(ZLIB::ZLIB STATIC IMPORTED)\n'
             '    set_target_properties(ZLIB::ZLIB PROPERTIES\n'
             '        IMPORTED_LOCATION "${CMAKE_BINARY_DIR}/3rdparty/zlib/zlib/${_og2_zlib_file}"')
    if os.path.isfile(fz):
        fzs = open(fz, encoding="utf-8").read()
        if "_og2_zlib_file" in fzs:
            print("  = already patched: FindZLIB.cmake")
        elif BROKEN in fzs:
            open(fz, "w", encoding="utf-8", newline="\n").write(fzs.replace(BROKEN, FIXED))
            print("  + patched: FindZLIB.cmake (zlib IMPORTED_LOCATION)")
        else:
            print("  !! FindZLIB.cmake shape changed -- if the MSVC build fails on a missing\n"
                  "     libzlibstatic.a, repoint ZLIB::ZLIB's IMPORTED_LOCATION at zs.lib by hand.")

    # 6. build-enablement fix: bundled wolfSSL sets OPENSSL_EXTRA (so curl calls
    #    wolfSSL_CTX_set1_groups_list) but WOLFSSL_TLS13=OFF -- and that function is only
    #    compiled under `WOLFSSL_TLS13 && HAVE_SUPPORTED_CURVES`, giving an unresolved
    #    external at the final rpcs3.exe link. Turning TLS13 on aligns wolfSSL with curl.
    ws = os.path.join(root, "3rdparty", "wolfssl", "CMakeLists.txt")
    if os.path.isfile(ws):
        wss = open(ws, encoding="utf-8").read()
        if 'set(WOLFSSL_TLS13 OFF CACHE INTERNAL "")' in wss:
            open(ws, "w", encoding="utf-8", newline="\n").write(
                wss.replace('set(WOLFSSL_TLS13 OFF CACHE INTERNAL "")',
                            'set(WOLFSSL_TLS13 ON CACHE INTERNAL "")'))
            print("  + patched: wolfssl CMakeLists (WOLFSSL_TLS13 ON)")
        elif 'set(WOLFSSL_TLS13 ON CACHE INTERNAL "")' in wss:
            print("  = already patched: wolfssl CMakeLists")
        else:
            print("  !! wolfssl WOLFSSL_TLS13 line changed -- if the link fails on\n"
                  "     wolfSSL_CTX_set1_groups_list, set WOLFSSL_TLS13 ON by hand.")

    print("\n" + ("ALL PATCHES APPLIED." if ok else "SOME PATCHES FAILED - see notes above."))
    print("""
Build (memory breakpoints ON). Verified toolchain: MSVC BuildTools 2022 (cl 14.44) +
Win SDK 10.x, CMake >=3.28 (4.x ok), Ninja, Qt6 (>=6.7) msvc2022_64 + qtmultimedia,
Vulkan SDK. Run inside a vcvars64 shell with Qt on CMAKE_PREFIX_PATH:

  cmake -G Ninja -S . -B build -DCMAKE_BUILD_TYPE=Release ^
    -DHAS_MEMORY_BREAKPOINTS=ON -DWITH_LLVM=ON -DBUILD_LLVM=ON ^
    -DLLVM_ENABLE_DIA_SDK=OFF -DCMAKE_DISABLE_FIND_PACKAGE_SDL3=ON ^
    -DCMAKE_POLICY_VERSION_MINIMUM=3.5 -DCMAKE_PREFIX_PATH=<Qt>/msvc2022_64 ^
    -DUSE_SYSTEM_ZLIB=OFF -DUSE_SYSTEM_CURL=OFF -DUSE_SYSTEM_OPENCV=OFF ^
    -DUSE_SYSTEM_SDL=OFF -DUSE_SYSTEM_FFMPEG=OFF
  cmake --build build --target rpcs3 -j
  # NOTE: this tree cannot be reconfigured in place unless SDL3 find is disabled
  # (CMAKE_DISABLE_FIND_PACKAGE_SDL3=ON) -- otherwise SDL's export() files re-included
  # on reconfigure abort it, forcing a full wipe + LLVM rebuild.

Use:
  1. Run YOUR build; Config -> CPU -> PPU Decoder = *Interpreter* (required).
  2. Boot the game to the target screen; find the address with the Memory Viewer
     (search the on-screen text, e.g. 'Soulgain').
  3. Debugger -> Add BP -> 'Memory Read' at that address. Leave 'Break on BPM' OFF.
  4. Interact with the screen so it redraws; every reading instruction is logged
     (deduped) to  og2_trace.log  in the RPCS3 working directory.
  5. python tools/trace_report.py <path>/og2_trace.log
     -> build/trace_reports/<name>.md : the reading PCs, ranked, with call stacks,
        annotated against known functions. Hand the top PC to the disassembly step.
""")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
