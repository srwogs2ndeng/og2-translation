#!/usr/bin/env python3
"""trace_report.py - digest an og2_trace.log (from the instrumented RPCS3 build)
into an actionable markdown report.

The patched RPCS3 (see docs/RE-INSTRUMENT-PLAN.md + tools/rpcs3_og2_trace.patch)
writes one durable, structured line per UNIQUE (type, guest-PC) hit:

    HIT R cia=0x005a5124 ea=0x300cf7ba val=0x53 lr=0x0051f2c0 st=0x0051f2c0>0x004a1180>0x00123456
    SUM R cia=0x005a5124 hits=482

This tool groups hits by watch type, sorts by hit count, annotates PCs against
the project's known-function map, and writes build/trace_reports/<name>.md.

Usage:
    python tools/trace_report.py <path-to-og2_trace.log> [report-name]

Typical loop: boot the instrumented RPCS3 (PPU Interpreter mode!), open the
target screen, quit RPCS3 (flushes SUM lines), run this, read the report,
hand the top PCs to the disassembly step (tools/eboot_analyze.py <cia>).
"""
import os, re, sys, datetime

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Known code landmarks from the project's RE so far - extend as we learn more.
KNOWN = [
    (0x0088038, 0x0088400, "line splitter (counts @/\\n breaks)"),
    (0x02A2A9C, 0x02A3200, "FUN_002a2a9c per-glyph quad draw (dialogue path)"),
    (0x029E808, 0x029E840, "text-layout width getter (+0x164)"),
    (0x029EA70, 0x029EB00, "text-layout object ctor"),
    (0x059F25C, 0x059F400, "desc-twin condense A (fdivs f26,f3,f13)"),
    (0x05A5124, 0x05A5300, "desc-twin condense B (fdivs f26,f3,f13)"),
    (0x05CD2D4, 0x05CD500, "menu condense (fdivs f0,f1,f5) - DO NOT clamp"),
    (0x05CDB98, 0x05CE000, "draw orchestrator (cached text obj r2+0x2100)"),
    (0x05CDF80, 0x05CE100, "UTF-8 char counter"),
    (0x05CE1A0, 0x05CE400, "dialogue caller region"),
    (0x061D7D4, 0x061DA00, "condense site (fdivs f26,f27,f5)"),
    (0x0A123F0, 0x0A149E0, "FUN_00a123f0 dialogue layout/renderer (K-patched)"),
    (0x0A149E8, 0x0A16000, "FUN_00a149e8 dialogue layout twin (K-patched)"),
    (0x0A1329C, 0x0A132A0, "dialogue condense A (fdivs f26,f2,f1)"),
    (0x0A15868, 0x0A15870, "dialogue condense B (fdivs f26,f2,f1)"),
    (0x0C45900, 0x0C46000, "OUR code caves (advance K / term-field / menu)"),
]


def annotate(cia):
    for lo, hi, name in KNOWN:
        if lo <= cia < hi:
            return name
    return ""


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    log = sys.argv[1]
    name = sys.argv[2] if len(sys.argv) > 2 else datetime.datetime.now().strftime("trace-%Y%m%d-%H%M%S")
    hits = {}    # (type, cia) -> dict(ea, val, lr, st)
    sums = {}    # (type, cia) -> count
    ranges = []
    for line in open(log, encoding="utf-8", errors="replace"):
        line = line.strip()
        if line.startswith("CFG "):
            ranges.append(line[4:]); continue
        m = re.match(r"HIT (\w) cia=0x([0-9a-fA-F]+) ea=0x([0-9a-fA-F]+) val=0x([0-9a-fA-F]+) lr=0x([0-9a-fA-F]+) st=(\S*)", line)
        if m:
            t, cia, ea, val, lr, st = m.groups()
            hits[(t, int(cia, 16))] = dict(ea=int(ea, 16), val=int(val, 16), lr=int(lr, 16), st=st)
            continue
        m = re.match(r"SUM (\w) cia=0x([0-9a-fA-F]+) hits=(\d+)", line)
        if m:
            t, cia, n = m.groups()
            sums[(t, int(cia, 16))] = int(n)
    outdir = os.path.join(REPO, "build", "trace_reports")
    os.makedirs(outdir, exist_ok=True)
    out = os.path.join(outdir, name + ".md")
    with open(out, "w", encoding="utf-8") as f:
        f.write(f"# og2 trace report - {name}\n\nsource: `{log}`\n\n")
        if ranges:
            f.write("## Watched ranges\n\n" + "\n".join(f"- `{r}`" for r in ranges) + "\n\n")
        for t, title in (("R", "Reads"), ("W", "Writes"), ("X", "Executions")):
            keys = [k for k in hits if k[0] == t]
            if not keys:
                continue
            keys.sort(key=lambda k: -sums.get(k, 1))
            f.write(f"## {title} ({len(keys)} unique PCs)\n\n")
            f.write("| guest PC | hits | first EA | val | LR | call stack | known? |\n")
            f.write("|---|---|---|---|---|---|---|\n")
            for k in keys:
                h = hits[k]
                f.write(f"| `0x{k[1]:07X}` | {sums.get(k, 1)} | `0x{h['ea']:08X}` | 0x{h['val']:X} "
                        f"| `0x{h['lr']:07X}` | `{h['st']}` | {annotate(k[1])} |\n")
            f.write("\n")
        f.write("## Next step\n\nDisassemble around the top unannotated PCs:\n"
                "`python tools/eboot_analyze.py` (or capstone at foff = cia - 0x10000 in the\n"
                "decrypted EBOOT.elf) and look for the advance/condense math near each PC.\n")
    print(f"wrote {out}  ({len(hits)} unique PCs, {len(ranges)} watch ranges)")


if __name__ == "__main__":
    main()
