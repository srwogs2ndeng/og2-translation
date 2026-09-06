#!/usr/bin/env python3
"""build_glossary.py - parse glossary/characters_source.md ("EN (JP)" pairs) into a
JP->EN glossary JSON used by the translation workflow for name consistency.

Also merges unit-name pairs derived from Battle *U8.csv when available (JP unit name
-> EN) if a units_source file is present. Output: glossary/glossary.json
"""
import re, json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GDIR = os.path.join(ROOT, "glossary")

PAIR = re.compile(r'([A-Za-z][^(,\n]*?)\s*\(([^)]+)\)')

def parse_pairs(text):
    # drop comment / blank lines so headers can't bleed into a name
    text = "\n".join(l for l in text.splitlines() if not l.lstrip().startswith("#"))
    out = {}
    for en, jp in PAIR.findall(text):
        en = en.strip().strip('"').strip()
        jp = jp.strip()
        # skip non-name parentheticals (English gloss in parens, etc.)
        if not jp or not re.search(r'[぀-ヿ一-鿿]', jp):
            continue
        out[jp] = en
    return out

def main():
    src = os.path.join(GDIR, "characters_source.md")
    chars = parse_pairs(open(src, encoding="utf-8").read())
    glossary = {"characters": chars}
    # also emit a flat jp->en map for quick lookup
    flat = dict(chars)
    glossary["flat"] = flat
    outp = os.path.join(GDIR, "glossary.json")
    json.dump(glossary, open(outp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"parsed {len(chars)} character JP->EN pairs -> {outp}")
    # sanity: print a few
    for i, (jp, en) in enumerate(list(chars.items())[:6]):
        print(f"  {jp} -> {en}")
    # flag suspicious (very short JP or dup EN)
    dups = {}
    for jp, en in chars.items():
        dups.setdefault(en, []).append(jp)
    multi = {en: js for en, js in dups.items() if len(js) > 1}
    if multi:
        print("note: EN names with multiple JP spellings:", {k: v for k, v in list(multi.items())[:5]})

if __name__ == "__main__":
    main()
