#!/usr/bin/env python3
"""fidelity_merge.py - merge the fidelity re-read findings into one review report.

Reads  build/audit/fidelity/out/*.json   (per-unit reviewer findings, report-only)
plus   build/audit/audit_report R11 items (cross-container term inconsistencies)
Writes build/audit/fidelity_findings.json (flat, machine-readable - the apply phase
       consumes this after the owner approves)
       build/audit/FIDELITY-REPORT.md      (human review document)

Re-runnable at any time; reflects however many units have completed so far.
"""
import json, glob, os, collections

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTD = os.path.join(REPO, "build", "audit", "fidelity", "out")
J = lambda p: json.load(open(p, encoding="utf-8"))

CHECK_DESC = {
    "E1": "residual Japanese", "E2": "romaji leak", "E3": "meaning error",
    "E4": "broken text", "E5": "canon-name violation",
    "A1": "translationese / stilted", "A2": "register mismatch", "P1": "polish",
}

def main():
    items = {i["name"]: i for i in J(os.path.join(REPO, "build/audit/fidelity/_items.json"))}
    outs = sorted(glob.glob(os.path.join(OUTD, "*.json")))
    finds, reviewed = [], 0
    for p in outs:
        d = J(p)
        reviewed += d.get("reviewed", 0)
        src = d.get("source", os.path.basename(p)[:-5])
        for f in d.get("findings", []):
            f["source"] = src
            f["tier"] = src.split("_")[0]
            finds.append(f)

    # fold in R11 term inconsistencies with a majority-pick recommendation
    r11 = []
    arp = os.path.join(REPO, "build", "audit_report.json")
    if os.path.isfile(arp):
        rep = J(arp)
        rep_items = rep if isinstance(rep, list) else rep.get("findings", rep.get("items", []))
        for it in rep_items:
            if it.get("rule") == "R11":
                r11.append(it.get("msg", ""))

    flat = {"units_done": len(outs), "units_total": len(items), "rows_reviewed": reviewed,
            "findings": finds, "r11_term_inconsistencies": r11}
    json.dump(flat, open(os.path.join(REPO, "build/audit/fidelity_findings.json"), "w",
              encoding="utf-8"), ensure_ascii=False, indent=1)

    by_check = collections.Counter(f.get("check", "?") for f in finds)
    by_tier = collections.Counter(f["tier"] for f in finds)
    by_sev = collections.Counter(f.get("severity", "?") for f in finds)

    L = []
    L.append("# Fidelity re-read - review report (REPORT-ONLY, nothing applied)\n")
    L.append(f"Progress: **{len(outs)}/{len(items)} units** - {reviewed:,} rows reviewed - "
             f"**{len(finds)} findings** ({by_sev.get('error',0)} error / "
             f"{by_sev.get('awkward',0)} awkward / {by_sev.get('polish',0)} polish)\n")
    L.append("| check | class | count |\n|---|---|---|")
    for c in ["E1","E2","E3","E4","E5","A1","A2","P1"]:
        if by_check.get(c): L.append(f"| {c} | {CHECK_DESC[c]} | {by_check[c]} |")
    L.append("")
    L.append("| tier | findings |\n|---|---|")
    for t, n in by_tier.most_common(): L.append(f"| {t} | {n} |")
    L.append("")

    def section(title, sel, cap=None):
        rows = [f for f in finds if sel(f)]
        if not rows: return
        L.append(f"\n## {title} ({len(rows)})\n")
        for f in rows[:cap] if cap else rows:
            L.append(f"### `{f['source']}` : `{f.get('key','?')}`  [{f.get('check','?')}]")
            L.append(f"- issue: {f.get('issue','')}")
            jp = (f.get('jp') or '').replace('\n', ' ')
            L.append(f"- jp: `{jp[:160]}`")
            L.append(f"- en: `{(f.get('en') or '')[:200]}`")
            L.append(f"- **proposed:** `{(f.get('proposed') or '')[:200]}`")
            L.append("")
        if cap and len(rows) > cap:
            L.append(f"*...and {len(rows)-cap} more (see fidelity_findings.json).*\n")

    section("Errors (wrong / broken / untranslated / canon)", lambda f: f.get("severity") == "error")
    section("Awkward (stilted, register)", lambda f: f.get("severity") == "awkward")
    section("Polish (optional)", lambda f: f.get("severity") == "polish", cap=60)

    if r11:
        L.append(f"\n## Cross-container term inconsistencies (R11, {len(r11)}) - pick one spelling each\n")
        for m in r11: L.append(f"- {m}")
        L.append("")

    md = os.path.join(REPO, "build/audit/FIDELITY-REPORT.md")
    open(md, "w", encoding="utf-8", newline="\n").write("\n".join(L))
    print(f"{len(outs)}/{len(items)} units, {reviewed:,} rows, {len(finds)} findings")
    print(f"-> {md}")
    print(f"-> {os.path.join(REPO,'build/audit/fidelity_findings.json')}")

if __name__ == "__main__":
    main()
