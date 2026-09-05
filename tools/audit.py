#!/usr/bin/env python3
"""audit.py - permanent QA suite for the OG2 translation (see docs/AUDIT-PLAN.md).

Every rule encodes a lesson learned in-game so that class of bug can never ship
again. Deterministic, zero model tokens, runs on py3.11+ (self-contained - does
NOT import reinsert_utf8, which needs 3.12). It re-derives `emit_en` exactly as
worksheet.apply does and measures UTF-8 bytes against each entry's stored slot.

    python tools/audit.py                       # human summary, all rules
    python tools/audit.py --json OUT.json        # full machine-readable dump
    python tools/audit.py --gate                 # exit 1 if any ERROR finding
    python tools/audit.py --only R2,R5           # run a subset
    python tools/audit.py --coverage             # Tier 2 empty-en / 0% report
    python tools/audit.py --sev ERROR            # only show >= this severity

Severity: ERROR = crash/corruption/silently-invisible in game (gate-blocking);
WARN = likely-visible defect; INFO = report-only (human judgement).
"""
import sys, os, json, glob, re, ast, collections

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WS = os.path.join(REPO, "build", "worksheets")
SEV = {"ERROR": 3, "WARN": 2, "INFO": 1}

# --- normalizer (kept in lockstep with worksheet.PUNCT; R0 verifies non-drift) ---
PUNCT = {
    "’": "'", "‘": "'", "ʼ": "'",
    "“": '"', "”": '"', "„": '"',
    "—": "-", "–": "-", "―": "-",
    "…": "...",
    " ": " ",
    "！": "!", "？": "?", "，": ",", "．": ".",
    "：": ":", "；": ";", "（": "(", "）": ")",
    "　": " ",
}
_TR = {ord(k): v for k, v in PUNCT.items()}


def normalize(text):
    return text.translate(_TR)


def rewrap(text, width=48):
    joined = " ".join(s.strip() for s in text.split("@") if s.strip())
    if len(joined) <= width:
        return joined
    out, line = [], ""
    for word in joined.split(" "):
        if not line:
            line = word
        elif len(line) + 1 + len(word) <= width:
            line += " " + word
        else:
            out.append(line); line = word
    if line:
        out.append(line)
    return "@".join(out)


# --- vocab (grounded in the real corpus) ---
CONTROL_TAGS = {"W", "H", "C", "S", "Y", "T", "I", "X", "LINK"}
WTD_MARK = os.path.join("Window", "WindowToolData")          # fullwidth markup allowed here
ENGINE_KEY = re.compile(r"^[\[［].+?[\]］]-")
TAG = re.compile(r"<(/?)([^>=\s]+)")
FULLWIDTH_ASCII = re.compile(r"[！-～]")             # fullwidth ! .. ~ (post-normalize residue)
DOUBLED = re.compile(r"(?<![.!?\"'「/@])\b([A-Z]\w{2,})\s+\1\b")  # mid-line Capitalized doubles only
# interjections legitimately repeat; the target is doubled PROPER NOUNS ("Kai Kai")
INTERJ = {"ow", "heh", "ha", "ho", "hee", "ah", "oh", "no", "hey", "yeah", "ugh", "haha",
          "tsk", "grr", "um", "uh", "woah", "whoa", "hah", "huff", "gah", "argh", "ngh",
          "nng", "hmph", "hup", "yah", "wah", "gwah", "gah", "run", "go", "now", "very"}
SUBST = re.compile(r"#\d")
KATA = re.compile(r"[぀-ヿ゠-ㇿ・ー]")               # katakana + long-vowel + middle dot
# exotic char classes that render wrong (the "Solgади" / "Ra¶ken" class). NOT § (special
# glyph token), NOT ♪ ▼ ● (UI glyphs the font has), NOT 「」・ (game punctuation).
CONFUSABLE = re.compile(r"[Ͱ-ϿЀ-ӿ]")               # cyrillic / greek lookalikes
COMBINING = re.compile(r"[̀-ͯ]")           # combining diacritics
LATIN_EXT = re.compile(r"[Ā-ɏ]")           # macrons ā ō, latin-extended
EXOTIC_LITERAL = set("¶†‡¦")
CJK = re.compile(r"[぀-ヿ゠-ㇿ一-鿿ぁ-ゟＡ-Ｚ]")
TERMLINK = re.compile(r"<([^<>=]+)>")   # <...> with no '=' inside: a term link, not a key=value tag


def is_dialogue(relpath):
    return "logic/talk/" in relpath.replace(os.sep, "/")


def is_growable(relpath):
    # LDBI dialogue (logic/talk) regrows; FixedData splice-grows (FIXH). Everything
    # else (Battle/Common/General2d/EBOOT) is in-place and slot-bounded.
    p = relpath.replace(os.sep, "/")
    return is_dialogue(relpath) or "FixedData" in p


def is_wtd(relpath):
    return WTD_MARK in relpath


def emit_en(v, dialogue):
    raw = v.get("en")
    if not raw:
        return None
    en = normalize(raw).strip()
    if dialogue:
        en = rewrap(en)
    return en


def tags_of(text, control_only=True):
    out = []
    for closer, head in TAG.findall(text or ""):
        if control_only and head not in CONTROL_TAGS:
            continue
        if control_only:
            out.append(("/" if closer else "") + head)
        else:
            out.append((closer, head))
    return out


def iter_entries():
    for wp in sorted(glob.glob(os.path.join(WS, "**", "*.json"), recursive=True)):
        rel = os.path.relpath(wp, WS)
        try:
            d = json.load(open(wp, encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(d, dict):
            continue
        # preserve file order (offset order) for neighbour-based rules
        items = list(d.items())
        yield rel, items


# ------------------------------------------------------------------- rules
def check(findings, rid, sev, rel, key, msg):
    findings.append({"rule": rid, "sev": sev, "file": rel, "key": key, "msg": msg})


def rule_R0(findings):
    """Normalizer non-drift: our PUNCT must equal worksheet.PUNCT."""
    src = open(os.path.join(REPO, "tools", "worksheet.py"), encoding="utf-8").read()
    tree = ast.parse(src)
    wp = None
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and any(
                getattr(t, "id", "") == "PUNCT" for t in node.targets):
            wp = ast.literal_eval(node.value)
    if wp is None:
        check(findings, "R0", "ERROR", "tools/worksheet.py", "-", "PUNCT map not found")
    elif wp != PUNCT:
        miss = set(wp) ^ set(PUNCT)
        check(findings, "R0", "ERROR", "tools/worksheet.py", "-",
              f"normalizer drift vs worksheet.PUNCT: differing keys {sorted(miss)!r}")


def run_entry_rules(findings, only):
    def on(r):
        return only is None or r in only
    for rel, items in iter_entries():
        dial = is_dialogue(rel)
        grow = is_growable(rel)
        wtd = is_wtd(rel)
        translated_flags = [(k, bool((v.get("en") or "").strip()) if isinstance(v, dict) else False)
                            for k, v in items]
        for idx, (key, v) in enumerate(items):
            if not isinstance(v, dict):
                continue
            jp = v.get("jp", "") or ""
            raw = v.get("en") or ""
            # R1 engine keys
            if on("R1") and ENGINE_KEY.search(jp) and raw.strip():
                check(findings, "R1", "ERROR", rel, key,
                      f"engine key must be en:\"\" (jp={jp[:24]!r} en={raw[:24]!r})")
            # R9 visible-empty (skip format/debug strings)
            if (on("R9") and jp.strip() and not raw.strip() and not ENGINE_KEY.search(jp)
                    and not re.search(r"[%\\{}]|0x[0-9A-Fa-f]", jp)):
                lo, hi = max(0, idx - 3), min(len(items), idx + 4)
                neigh = [translated_flags[j][1] for j in range(lo, hi) if j != idx]
                short = len(jp) <= 12 and "@" not in jp and "\n" not in jp
                if short and neigh and sum(neigh) >= 0.6 * len(neigh):
                    check(findings, "R9", "WARN", rel, key,
                          f"likely visible stray: empty-en label among translated rows (jp={jp!r})")
            en = emit_en(v, dial)
            if en is None:
                continue
            b = en.encode("utf-8")
            slot = v.get("slot")
            # R2 slot overflow. reinsert_grow repoints an over-slot entry IFF it has a
            # discoverable pointer (_detect_tables); pointer-less ones land in `refused`
            # and silently stay JP. Slot alone can't tell which, so this is a WARN
            # heads-up - the deploy's own "REFUSED (left original)" line is authoritative.
            # EBOOT is EXCLUDED: it is built by build_eboot.py (not deploy apply), whose
            # keys are ambiguous VA/file offsets resolved by JP-byte match, so the
            # worksheet `slot` field does not reflect the real applied slot. build_eboot's
            # own "too-long N" count is the authority for EBOOT overflow.
            if on("R2") and not grow and "EBOOT" not in rel and isinstance(slot, int) and len(b) > slot:
                check(findings, "R2", "WARN", rel, key,
                      f"over-slot {len(b)}>{slot}B -> stays JP unless pointer-repointed "
                      f"(confirm via deploy REFUSED report) (en={en[:36]!r})")
            # R3 exotic chars (confusables that render wrong; § ♪ ▼ etc. are legit)
            if on("R3"):
                bad = [ch for ch in en if CONFUSABLE.match(ch) or COMBINING.match(ch)
                       or LATIN_EXT.match(ch) or ch in EXOTIC_LITERAL]
                if bad:
                    u = "/".join("%04X" % ord(c) for c in sorted(set(bad)))
                    check(findings, "R3", "ERROR", rel, key,
                          f"exotic char(s) {''.join(sorted(set(bad)))!r} (U+{u}) in en={en[:40]!r}")
            # R4 tokens
            if on("R4"):
                if jp.count("§") != en.count("§"):
                    check(findings, "R4", "ERROR", rel, key,
                          f"§ count jp={jp.count(chr(0xa7))} en={en.count(chr(0xa7))}")
                for s in set(SUBST.findall(jp)):
                    if s not in en:
                        check(findings, "R4", "ERROR", rel, key, f"lost substitution {s} (en={en[:40]!r})")
                # bracket drop: only when JP is a self-balanced quote but EN isn't.
                # Skips spanning quotes (JP itself unbalanced) and 「」->"" conversion
                # (EN 0/0 is still balanced) - neither is a bug.
                if jp.count("「") == jp.count("」") and en.count("「") != en.count("」"):
                    check(findings, "R4", "ERROR", rel, key,
                          f"unbalanced 「」 in en ({en.count(chr(0x300c))}/{en.count(chr(0x300d))}), "
                          f"jp balanced ({jp.count(chr(0x300c))})")
            # R5 control-tag match
            if on("R5"):
                jt, et = collections.Counter(tags_of(jp)), collections.Counter(tags_of(en))
                if jt != et:
                    diff = {t: et.get(t, 0) - jt.get(t, 0) for t in set(jt) | set(et)
                            if et.get(t, 0) != jt.get(t, 0)}
                    check(findings, "R5", "ERROR", rel, key, f"control-tag mismatch jp->en {diff}")
            # R6 term-link: any <...> whose content is a readable NAME (not a key=value
            # control tag, not a closer, not the KeyWords tag) is a glossary term link.
            # The engine draws it full-width in the oversized ~1.67x field -> the line
            # goes wide/gappy and slips off the box edge (the dialogue "slippage" class,
            # same renderer bug as the library). WARN: the fix is strip (plaintext) or the
            # term-field EBOOT patch, not a data corruption.
            if on("R6") and not wtd:
                leaks = []
                for c in TERMLINK.findall(en):
                    c = c.strip()
                    head = re.split(r"[=\s]", c)[0] if c else ""
                    if (c.startswith("/") or head in CONTROL_TAGS or head == "KeyWords"
                            or "%" in c or not re.search(r"[A-Za-z぀-鿿]", c)):
                        continue  # skip control tags, closers, printf formats, non-text
                    leaks.append(c)
                if leaks:
                    check(findings, "R6", "WARN", rel, key, f"<term> link renders full-width -> slippage: {leaks[:4]}")
            # R7 fullwidth ASCII outside WTD
            if on("R7") and not wtd and FULLWIDTH_ASCII.search(en):
                fw = FULLWIDTH_ASCII.findall(en)
                check(findings, "R7", "WARN", rel, key, f"fullwidth ASCII {fw[:6]} in en={en[:40]!r}")
            # R8 doubled proper nouns - but skip doublings that MIRROR a JP reduplication
            # (イティイティ島 "Iti Iti", ＢＬＵＥ　ＢＬＵＥ "BLUE BLUE" are faithful, not bugs;
            # グルンガスト改 -> "Kai Kai" is a bug - 改 appears once in JP).
            if on("R8") and not re.search(r"(.{2,})[\s　]?\1", jp):
                for m in DOUBLED.finditer(en):
                    if m.group(1).lower() not in INTERJ:
                        check(findings, "R8", "WARN", rel, key, f"doubled word {m.group(0)!r} in en={en[:48]!r}")
                        break
            # R12 dialogue reflow > 3 lines
            if on("R12") and dial and len(en.split("@")) > 3:
                check(findings, "R12", "WARN", rel, key, f"reflows to {len(en.split('@'))} lines (box truncates)")
            # R13 stray semicolon in dialogue. The message engine reads ';@' as a
            # choice-option separator; a bare ';' in narration makes the following
            # words render as a spurious highlighted option (the "I can't" bug). Real
            # choice-list rows use ';@' only, so ';' not followed by '@' is the tell.
            # check RAW en (choice rows are ';@'; reflow would turn '@' into a space
            # and mask the distinction), not the emitted/reflowed text.
            if on("R13") and dial and re.search(r";(?!@)", raw):
                check(findings, "R13", "WARN", rel, key,
                      f"bare ';' in dialogue parses as choice-option split; use . / , / - instead (en={raw[:48]!r})")


def rule_R10(findings, only):
    if not (only is None or "R10" in only):
        return
    path = os.path.join(REPO, "build", "pdf_charnames.json")
    if not os.path.exists(path):
        return
    names = json.load(open(path, encoding="utf-8"))
    for rel, items in iter_entries():
        dial = is_dialogue(rel)
        for key, v in items:
            if not isinstance(v, dict):
                continue
            jp = v.get("jp", "") or ""
            en = emit_en(v, dial)
            if not en:
                continue
            for jn, ename in names.items():
                if len(jn) < 3 or not ename:
                    continue
                pos = jp.find(jn)
                if pos < 0:
                    continue
                # boundary: reject if the JP name sits inside a longer katakana run
                # (e.g. クロ inside クロス "Cross") - that's a different word, not the name
                before = jp[pos - 1] if pos > 0 else ""
                after = jp[pos + len(jn)] if pos + len(jn) < len(jp) else ""
                if KATA.match(before) or KATA.match(after):
                    continue
                if ename.lower() in en.lower():
                    continue
                # partial credit: any distinctive word of the canonical spelling present -> ok
                if any(w for w in re.split(r"\W+", ename) if len(w) > 3 and w.lower() in en.lower()):
                    continue
                check(findings, "R10", "WARN", rel, key,
                      f"name canon: jp has {jn!r} -> expected {ename!r} (en={en[:48]!r})")
                break


def rule_R11(findings, only):
    if not (only is None or "R11" in only):
        return
    # short JP UI terms (<=8 chars, no punctuation) mapped to their EN variants
    m = collections.defaultdict(lambda: collections.Counter())
    for rel, items in iter_entries():
        dial = is_dialogue(rel)
        for key, v in items:
            if not isinstance(v, dict):
                continue
            jp = (v.get("jp", "") or "").strip()
            en = emit_en(v, dial)
            # UI/menu terms only: skip conversational 「…」 lines (natural EN variety is fine)
            # and skip dialogue containers - term consistency is a menu/label concern
            if (en and not dial and 1 <= len(jp) <= 8 and "　" not in jp and "@" not in jp
                    and "\n" not in jp and CJK.search(jp)
                    and "「" not in en and "」" not in en
                    and re.sub(r"[\"'.…\s]", "", en)):
                m[jp][en] += 1
    for jp, variants in sorted(m.items()):
        if len(variants) > 1:
            top = variants.most_common()
            check(findings, "R11", "INFO", "(cross-container)", jp,
                  f"same JP term {jp!r} -> {len(variants)} EN spellings: {dict(top)}")


def _lev2(a, b):
    """Levenshtein capped at 3 (returns 9 past that)."""
    if abs(len(a) - len(b)) > 2:
        return 9
    n = len(b)
    prev = list(range(n + 1))
    for i in range(1, len(a) + 1):
        cur = [i] + [0] * n
        for j in range(1, n + 1):
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (a[i - 1] != b[j - 1]))
        prev = cur
    return prev[n]


def rule_R14(findings, only):
    """Phonetic-garble detector: a JP katakana term that matches the game's own
    weapon glossary but is rendered in EN as a made-up (non-dictionary, non-canon)
    token - the 'Boosted Rihou' (should be Rifle) class that no regex/reviewer
    catches. Dual-gate for precision: (1) EN contains a made-up capitalized token,
    (2) a JP katakana run exactly/closely matches a WeaponData/MapWeaponData name
    whose canonical EN word is absent from the line."""
    if not (only is None or "R14" in only):
        return
    try:
        words = set(w.strip().lower() for w in open("/usr/share/dict/words", encoding="utf-8"))
    except OSError:
        return  # no wordlist -> rule unavailable
    known = set()
    for cf in ("pdf_charnames.json", "canon_names.json"):
        p = os.path.join(REPO, "build", cf)
        if os.path.exists(p):
            for v in json.load(open(p, encoding="utf-8")).values():
                if isinstance(v, str):
                    known.update(w.lower() for w in re.findall(r"[A-Za-z]+", v))
    glos = {}
    # authoritative in-game glossaries: weapon tables + the unit (mech) table
    for wf in ("WeaponData.dat.json", "MapWeaponData.dat.json", "UnitData.dat.json"):
        p = os.path.join(REPO, "build", "worksheets", "Logic", "Dat", "FixedData", wf)
        if not os.path.exists(p):
            continue
        for v in json.load(open(p, encoding="utf-8")).values():
            if isinstance(v, dict) and v.get("jp") and v.get("en") \
                    and re.search(r"[ァ-ヶ]", v["jp"]) and v["en"] not in ("Dummy", ""):
                glos[v["jp"]] = v["en"]
                known.update(w.lower() for w in re.findall(r"[A-Za-z]+", v["en"]))
    # validated in-game short-forms / brand aliases that are NOT garbles: teach
    # the glossary so the fuzzy matcher resolves to the correct short name rather
    # than flagging it against the full unit name. コンパチ ("Compati") is the
    # official brand romanization (cf. the "Compati Hero" series); コンパチカイザー
    # is the canonical short name the mech debuted under (The Great Battle IV),
    # distinct from the full コンパチブルカイザー / "Compatible Kaiser".
    for ajp, aen in {"コンパチカイザー": "Compati Kaiser"}.items():
        glos[ajp] = aen
        known.update(w.lower() for w in re.findall(r"[A-Za-z]+", aen))
    if not glos:
        return
    krun = re.compile(r"[ァ-ヶー・]{4,}")
    cap = re.compile(r"\b[A-Z][a-z]{2,}\b")
    for rel, items in iter_entries():
        for key, v in items:
            if not isinstance(v, dict):
                continue
            jp = v.get("jp") or ""
            en = v.get("en") or ""
            if not en or not jp:
                continue
            garble = [t for t in cap.findall(en)
                      if t.lower() not in words and t.lower() not in known]
            if not garble:
                continue                      # gate 1: made-up token present
            for run in krun.findall(jp):
                best, bd = None, 99
                for gjp in glos:
                    d = _lev2(run, gjp)
                    if d < bd:
                        bd, best = d, gjp
                if best is None or not (bd == 0 or (bd <= 2 and len(run) >= 7)):
                    continue                  # gate 2: solid weapon match
                cw = [w for w in re.findall(r"[A-Za-z]+", glos[best]) if len(w) >= 4]
                if cw and any(w.lower() not in en.lower() for w in cw):
                    check(findings, "R14", "WARN", rel, key,
                          f"phonetic garble {garble}: JP {run!r} = weapon {glos[best]!r}, "
                          f"but EN reads {en[:40]!r}")
                    break


FIXER_OWNED = ("KeyWordData.dat", "PilotDictionaryData.dat", "UnitDictionaryData.dat")


def coverage_report():
    print("=== Tier 2 coverage ===")
    per_file = []
    for rel, items in iter_entries():
        tot = sum(1 for _, v in items if isinstance(v, dict) and (v.get("jp", "") or "").strip())
        done = sum(1 for _, v in items if isinstance(v, dict)
                   and (v.get("jp", "") or "").strip() and (v.get("en") or "").strip())
        if tot:
            per_file.append((done / tot, done, tot, rel))
    per_file.sort()
    # the 3 fixer-owned files (HANDOFF sec 3) are BLANK BY DESIGN - text comes from
    # *_desc_en.json via fix_*.py, not the worksheet. 0% there is expected, not a gap.
    zero = [p for p in per_file if p[1] == 0 and not any(fx in p[3] for fx in FIXER_OWNED)]
    print(f"files: {len(per_file)}  |  genuine 0% files: {len(zero)} "
          f"(excludes {len(FIXER_OWNED)} fixer-owned blank-by-design)")
    ws_by_rel = {rel: items for rel, items in iter_entries()}
    for _, done, tot, rel in zero[:40]:
        items = ws_by_rel.get(rel, [])
        jps = [v.get("jp", "") for _, v in items if isinstance(v, dict) and (v.get("jp", "") or "").strip()]
        keyrate = sum(1 for j in jps if ENGINE_KEY.search(j)) / max(1, len(jps))
        tag = ("all engine-keys -> correctly en:\"\"" if keyrate > 0.95
               else "dev/authoring notes (not player-facing)" if "Summary" in rel or "Resource" in rel
               else "REAL GAP - translate")
        print(f"  0/{tot:>5}  {rel}  [{tag}]")
    # empty-en clustered classification, EBOOT focus
    for rel, items in iter_entries():
        if "EBOOT" not in rel:
            continue
        flags = [(bool((v.get("en") or "").strip()) if isinstance(v, dict) else False) for _, v in items]
        vis, dbg, unk = [], [], []
        for i, (key, v) in enumerate(items):
            if not isinstance(v, dict):
                continue
            jp = v.get("jp", "") or ""
            if not jp.strip() or (v.get("en") or "").strip():
                continue
            lo, hi = max(0, i - 3), min(len(items), i + 4)
            neigh = sum(flags[j] for j in range(lo, hi) if j != i)
            short = len(jp) <= 12 and re.search(r"[぀-ヿ一-鿿]", jp)
            if short and neigh >= 3:
                vis.append((key, jp))
            elif re.search(r"[%\\{}]|^0x|^[A-Za-z_]+$", jp):
                dbg.append((key, jp))
            else:
                unk.append((key, jp))
        print(f"\nEBOOT empty-en: visible-neighbour={len(vis)} debug/format={len(dbg)} unknown={len(unk)}")
        for key, jp in vis[:30]:
            print(f"  VISIBLE {key} jp={jp!r}")


def main():
    args = sys.argv[1:]
    only = None
    minsev = 1
    jsonout = None
    if "--only" in args:
        only = set(args[args.index("--only") + 1].split(","))
    if "--sev" in args:
        minsev = SEV[args[args.index("--sev") + 1]]
    if "--json" in args:
        jsonout = args[args.index("--json") + 1]
    if "--coverage" in args:
        coverage_report(); return 0

    findings = []
    rule_R0(findings)
    run_entry_rules(findings, only)
    # R10 (name canon) DISABLED by owner 2026-07-10: names are canon as-is, no audit.
    # Kept in code (rule_R10) and re-enableable via --only R10.
    if only and "R10" in only:
        rule_R10(findings, only)
    rule_R11(findings, only)
    rule_R14(findings, only)

    findings = [f for f in findings if SEV[f["sev"]] >= minsev]
    if jsonout:
        json.dump(findings, open(jsonout, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    by_rule = collections.Counter((f["rule"], f["sev"]) for f in findings)
    errs = sum(1 for f in findings if f["sev"] == "ERROR")
    print("=== audit summary ===")
    for (rid, sev), n in sorted(by_rule.items()):
        print(f"  {rid:4} {sev:5} {n}")
    print(f"total {len(findings)}  (ERROR {errs})")
    # a few examples per rule
    shown = collections.Counter()
    for f in findings:
        if shown[f["rule"]] < 4:
            print(f"  [{f['rule']}/{f['sev']}] {f['file']} {f['key']}: {f['msg']}")
            shown[f["rule"]] += 1
    if jsonout:
        print(f"full dump -> {jsonout}")
    if "--gate" in args:
        return 1 if errs else 0
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    sys.exit(main())
