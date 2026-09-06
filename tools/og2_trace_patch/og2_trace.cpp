// og2_trace.cpp - implementation of the OG2 memory-access tracer (see og2_trace.hpp).
// Add this file to rpcs3/Emu/CMakeLists.txt sources (the applier does it), or compile
// into rpcs3_emu. Only active when RPCS3_HAS_MEMORY_BREAKPOINTS is defined.
#include "og2_trace.hpp"

#ifdef RPCS3_HAS_MEMORY_BREAKPOINTS

#include "Emu/Cell/PPUThread.h"

namespace og2
{
	void hit(char type, u32 ea, u64 val, ppu_thread& ppu)
	{
		// ppu_thread is complete in this TU (PPUThread.h included below), so read the
		// guest PC / link register here instead of at the (possibly incomplete-type) call site.
		const u32 cia = ppu.cia;
		const u64 key = (static_cast<u64>(type) << 40) | cia;
		{
			std::lock_guard lock(g_mtx);
			if (!g_seen.insert(key).second)
				return;  // already logged this (type, PC) - one durable line each
			std::FILE* fp = file();
			if (!fp)
				return;

			// shallow call stack: caller PCs walked from the frame pointer
			std::string st;
			auto frames = ppu.dump_callstack_list();
			for (usz i = 0; i < frames.size() && i < 5; i++)
			{
				char b[16];
				std::snprintf(b, sizeof(b), "%s0x%06x", i ? ">" : "", frames[i].first);
				st += b;
			}
			if (st.empty())
				st = "-";

			std::fprintf(fp, "HIT %c cia=0x%06x ea=0x%08x val=0x%llx lr=0x%06x st=%s\n",
				type, cia, ea, static_cast<unsigned long long>(val),
				static_cast<u32>(ppu.lr), st.c_str());
			std::fflush(fp);  // durable immediately - survives a crash/forced-quit
		}
	}

	// ---- execution-PC register logger (see og2_trace.hpp) ----
	static std::vector<std::pair<u32, u32>> g_xranges;  // watched [lo,hi] guest-PC ranges
	static std::unordered_map<u32, int> g_xcount;        // per-PC hit counter (cap flood)
	static const int g_xcap = 40;                        // max logged hits per unique PC

	// Parse "lo-hi,pc,..." (hex) into out.
	static void parse_watch(const char* p, std::vector<std::pair<u32, u32>>& out)
	{
		while (p && *p)
		{
			while (*p == ',' || *p == ' ' || *p == ';' || *p == '\t' || *p == '\n' || *p == '\r') p++;
			if (!*p) break;
			char* end = nullptr;
			unsigned long lo = std::strtoul(p, &end, 16);
			unsigned long hi = lo;
			if (end && *end == '-')
				hi = std::strtoul(end + 1, &end, 16);
			out.emplace_back(static_cast<u32>(lo), static_cast<u32>(hi));
			p = (end && end != p) ? end : p + 1;
		}
	}

	static void log_watch(const char* how)
	{
		if (std::FILE* fp = file())
		{
			std::fprintf(fp, "CFG xwatch(%s)", how);
			if (g_xranges.empty()) std::fprintf(fp, " <cleared - full speed>");
			for (const auto& r : g_xranges) std::fprintf(fp, " 0x%x-0x%x", r.first, r.second);
			std::fprintf(fp, " cap=%d\n", g_xcap);
			std::fflush(fp);
		}
	}

	static std::string read_named_file(const char* name)
	{
		std::string s;
		if (std::FILE* f = std::fopen(name, "rb"))
		{
			char buf[512];
			usz n;
			while ((n = std::fread(buf, 1, sizeof(buf), f)) > 0) s.append(buf, n);
			std::fclose(f);
		}
		return s;
	}

	static std::string g_xfile_cache;
	static bool g_xfile_seen = false;

	// file-driven memory-read BP state (og2_membp.txt), same "lo-hi,pc,..." syntax
	static std::vector<std::pair<u32, u32>> g_mbranges;
	static std::unordered_map<u32, int> g_mbcount;
	static const int g_mbcap = 80;             // max logged reads per unique guest EA
	static std::string g_mbfile_cache;
	static bool g_mbfile_seen = false;

	// Called periodically from the interpreter loop (OG2_XPOLL). Re-reads BOTH og2_xwatch.txt
	// (exec watch) and og2_membp.txt (memory-read BP) and retargets them live; writing an
	// empty file clears that one. Runs at full speed when no exec watch is active.
	void xreload_if_changed()
	{
		std::string cur = read_named_file("og2_xwatch.txt");  // I/O outside the lock
		std::string mb  = read_named_file("og2_membp.txt");
		std::lock_guard lock(g_mtx);
		if (!(g_xfile_seen && cur == g_xfile_cache))          // exec watch changed
		{
			g_xfile_seen = true;
			g_xfile_cache = cur;
			g_xranges.clear();
			g_xcount.clear();  // reset per-PC caps so the new watch gets a fresh budget
			// The word "precise" anywhere in the file forces per-instruction stepping so
			// MID-block PCs are seen (input-killing slowdown). Omit it to watch BLOCK-ENTRY
			// PCs (function entries / branch targets) at FULL SPEED with input live. Strip
			// the word before parsing so it isn't mis-read as a hex range.
			std::string cleaned = cur;
			bool want_precise = false;
			for (const char* w : {"precise", "PRECISE", "Precise"})
			{
				usz p;
				while ((p = cleaned.find(w)) != std::string::npos)
				{
					cleaned.erase(p, std::strlen(w));
					want_precise = true;
				}
			}
			g_xprecise.store(want_precise);
			parse_watch(cleaned.c_str(), g_xranges);
			g_xactive.store(!g_xranges.empty());
			log_watch(want_precise ? "file/precise" : "file/fullspeed");
		}
		if (!(g_mbfile_seen && mb == g_mbfile_cache))         // memory-BP set changed
		{
			g_mbfile_seen = true;
			g_mbfile_cache = mb;
			g_mbranges.clear();
			g_mbcount.clear();
			parse_watch(mb.c_str(), g_mbranges);
			g_membp_active.store(!g_mbranges.empty());
			if (std::FILE* fp = file())
			{
				std::fprintf(fp, "CFG membp(file)");
				if (g_mbranges.empty()) std::fprintf(fp, " <cleared>");
				for (const auto& r : g_mbranges) std::fprintf(fp, " 0x%x-0x%x", r.first, r.second);
				std::fprintf(fp, " cap=%d\n", g_mbcap);
				std::fflush(fp);
			}
		}
	}

	// Startup: seed from env OG2_XWATCH (og2_xwatch.txt then takes over at runtime).
	static bool xinit()
	{
		if (const char* e = std::getenv("OG2_XWATCH"); e && *e)
			parse_watch(e, g_xranges);
		g_xactive.store(!g_xranges.empty());
		if (!g_xranges.empty()) log_watch("env");
		return true;
	}
	static const bool g_xinited = xinit();

	bool xwatch(u32 cia)
	{
		std::lock_guard lock(g_mtx);
		for (const auto& r : g_xranges)
		{
			if (cia >= r.first && cia <= r.second)
			{
				int& c = g_xcount[cia];
				if (c < g_xcap) { c++; return true; }
				return false;  // this PC hit its cap; stop logging it
			}
		}
		return false;
	}

	void xhit(ppu_thread& ppu)
	{
		std::lock_guard lock(g_mtx);
		std::FILE* fp = file();
		if (!fp) return;
		std::fprintf(fp, "X 0x%06x lr=0x%06x", static_cast<u32>(ppu.cia), static_cast<u32>(ppu.lr));
		for (int i = 0; i < 32; i++)
			std::fprintf(fp, " r%d=0x%llx", i, static_cast<unsigned long long>(ppu.gpr[i]));
		for (int i = 0; i < 32; i++)
			std::fprintf(fp, " f%d=%g", i, static_cast<double>(ppu.fpr[i]));
		std::fprintf(fp, "\n");
		std::fflush(fp);
	}

	// File-driven memory-read BP: if `ea` is in the og2_membp.txt set, dump full register
	// state + shallow callstack. Runs at FULL SPEED (no precise mode) so game input keeps
	// working while we capture a renderer's registers as it reads a known buffer. Per-EA cap.
	void membp(char type, u32 ea, ppu_thread& ppu)
	{
		std::lock_guard lock(g_mtx);
		bool in = false;
		for (const auto& r : g_mbranges)
			if (ea >= r.first && ea <= r.second) { in = true; break; }
		if (!in) return;
		int& c = g_mbcount[ea];
		if (c >= g_mbcap) return;  // this EA hit its cap; stop logging it
		c++;
		std::FILE* fp = file();
		if (!fp) return;
		std::string st;
		auto frames = ppu.dump_callstack_list();
		for (usz i = 0; i < frames.size() && i < 6; i++)
		{
			char b[16];
			std::snprintf(b, sizeof(b), "%s0x%06x", i ? ">" : "", frames[i].first);
			st += b;
		}
		std::fprintf(fp, "M %c ea=0x%08x cia=0x%06x lr=0x%06x", type, ea,
			static_cast<u32>(ppu.cia), static_cast<u32>(ppu.lr));
		for (int i = 0; i < 32; i++)
			std::fprintf(fp, " r%d=0x%llx", i, static_cast<unsigned long long>(ppu.gpr[i]));
		for (int i = 0; i < 32; i++)
			std::fprintf(fp, " f%d=%g", i, static_cast<double>(ppu.fpr[i]));
		std::fprintf(fp, " st=%s\n", st.c_str());
		std::fflush(fp);
	}
}

#endif
