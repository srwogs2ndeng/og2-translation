// og2_trace.hpp - durable memory-access tracer for the OG2 RE effort.
//
// Rides on RPCS3's built-in memory breakpoints (build with -DUSE_MEMORY_BREAKPOINTS=ON,
// which sets RPCS3_HAS_MEMORY_BREAKPOINTS). When the guest reads/writes an address that
// has a memory breakpoint set (via the normal debugger "Add BP -> Memory Read/Write"
// UI), the two existing checkpoints (ppu_feed_data for reads, vm::write* for writes)
// call og2_trace_hit(). Instead of pausing, we LOG one durable, structured line per
// UNIQUE (type, guest-PC) - the guest PC, the effective address, the value, the link
// register, and a shallow call stack - then CONTINUE. One playthrough of a screen thus
// captures every instruction that touches the watched memory, in a file you can read
// and act on with tools/trace_report.py.
//
// Output: <rpcs3 working dir>/og2_trace.log  (append; deduped, so it stays small).
// Toggle pausing separately with the debugger's "Break on BPM" - leave it OFF to trace.
#pragma once

#ifdef RPCS3_HAS_MEMORY_BREAKPOINTS

#include "util/types.hpp"
#include <cstdio>
#include <set>
#include <mutex>
#include <atomic>
#include <type_traits>
#include <vector>
#include <utility>
#include <unordered_map>
#include <string>
#include <cstdlib>
#include <cstring>

class ppu_thread;  // fwd; real def included by the .cpp sites that call us

namespace og2
{
	// Safely coerce any load/store value to u64 for logging. Integral and be_t<>
	// values convert; vector (v128) and other non-convertible types log as 0.
	template <typename T>
	inline u64 val64(const T& v)
	{
		if constexpr (std::is_convertible_v<T, u64>)
			return static_cast<u64>(v);
		else
			return 0;
	}

	inline std::mutex g_mtx;
	inline std::set<u64> g_seen;              // key = (type<<40) | cia  -> dedup
	inline std::atomic<bool> g_open{false};
	inline std::FILE* g_fp = nullptr;

	inline std::FILE* file()
	{
		if (!g_open.exchange(true))
		{
			g_fp = std::fopen("og2_trace.log", "a");
			if (g_fp)
				std::fprintf(g_fp, "CFG session-start\n");
		}
		return g_fp;
	}

	// Defined in og2_trace.cpp. Reads cia/lr/callstack from ppu THERE, where the full
	// ppu_thread definition is available. The call sites (esp. vm.h, which only
	// forward-declares ppu_thread) must NOT dereference ppu themselves -- binding *ppu
	// to this reference needs no completeness, but `ppu->cia` at the call site does not
	// compile against an incomplete type.
	void hit(char type, u32 ea, u64 val, ppu_thread& ppu);

	// --- execution-PC register logger (independent of the memory BP UI) ---
	// Watch set parsed once at startup from env OG2_XWATCH: comma-separated guest PCs
	// and lo-hi ranges, hex, e.g. "0x82c964,0x290204-0x2904ac". When the interpreter is
	// about to run an instruction whose PC is in the set, dump cia/lr/GPRs/FPRs (capped
	// per-PC so per-glyph code can't flood the log). g_xactive stays false unless
	// OG2_XWATCH is set, so the per-instruction cost is one relaxed atomic load.
	inline std::atomic<bool> g_xactive{false};
	// Precise (one-instruction-per-loop) mode is now DECOUPLED from g_xactive: it is only
	// engaged when the watch file explicitly asks for it (token "precise"). Without it, the
	// main-loop OG2_XTRACE still fires on every BLOCK-ENTRY PC (function entries, branch
	// targets) at FULL SPEED -> we can watch a renderer's entry (e.g. the scaled-text draw)
	// and dump its registers while game input stays live. Precise is only needed to catch
	// MID-block PCs, at the cost of the input-killing slowdown.
	inline std::atomic<bool> g_xprecise{false};
	bool xwatch(u32 cia);       // in a watched range AND under the per-PC cap (increments)
	void xhit(ppu_thread& ppu); // logs "X cia lr r0..r31 f0..f13"

	// Runtime-retargetable watch: og2_xwatch.txt in the RPCS3 working dir is re-read
	// periodically, so the watch can be changed (or cleared, restoring full speed)
	// WITHOUT relaunching + rebooting the game. Same syntax as OG2_XWATCH.
	inline std::atomic<u64> g_xtick{0};
	void xreload_if_changed();  // cheap no-op unless the file's contents actually changed

	// --- file-driven memory-read BP with FULL register dump (NO debugger UI needed) ---
	// og2_membp.txt (RPCS3 working dir, same syntax as og2_xwatch.txt) lists guest read
	// addresses / ranges. When the guest READS an address in the set, dump cia/lr/all
	// GPRs+FPRs + callstack at FULL SPEED (does NOT force precise mode) -> captures a
	// renderer's registers the moment it reads a known buffer, while game input still
	// works. Reloaded live by the same xreload poll. g_membp_active is false unless the
	// file is non-empty, so the per-read cost is one relaxed atomic load when idle.
	inline std::atomic<bool> g_membp_active{false};
	void membp(char type, u32 ea, ppu_thread& ppu);
}

#define OG2_TRACE(type, ea, val, ppu) ::og2::hit((type), (ea), ::og2::val64(val), (ppu))
#define OG2_XTRACE(ppu) do { if (::og2::g_xactive.load(std::memory_order_relaxed) && ::og2::xwatch((ppu).cia)) ::og2::xhit(ppu); } while (0)
// When a watch is active, force the threaded interpreter into precise (one-instruction-
// per-loop) mode so OG2_XTRACE sees EVERY guest PC, not just block entries. Expands to a
// cheap relaxed atomic load; OR it into the dispatch loop's next_fn ternary. Now gated by
// g_xprecise (set only when the watch file contains "precise"), NOT by g_xactive -- so a
// bare code-address watch runs at full speed and only block-entry PCs are seen.
#define OG2_XPRECISE (::og2::g_xprecise.load(std::memory_order_relaxed))
// Poll og2_xwatch.txt every ~4M instructions (a fraction of a second) so the watch can be
// retargeted live. Cost when idle is one relaxed increment + mask test per instruction.
#define OG2_XPOLL() do { if ((::og2::g_xtick.fetch_add(1, std::memory_order_relaxed) & 0x3FFFFF) == 0) ::og2::xreload_if_changed(); } while (0)
// File-driven memory-read BP (full register dump). Cheap relaxed atomic load when idle.
#define OG2_MEMBP(type, ea, ppu) do { if (::og2::g_membp_active.load(std::memory_order_relaxed)) ::og2::membp((type), (ea), (ppu)); } while (0)

#else
#define OG2_TRACE(type, ea, val, ppu) ((void)0)
#define OG2_XTRACE(ppu) ((void)0)
#define OG2_XPRECISE (false)
#define OG2_XPOLL() ((void)0)
#define OG2_MEMBP(type, ea, ppu) ((void)0)
#endif
