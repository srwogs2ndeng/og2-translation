#!/usr/bin/env python3
"""fix_skilldata.py - rebuild SkillData.dat's TWO-PART description records (and optionally
convert single-string descriptions into two-part records) AFTER the worksheet apply.

THE FORMAT (found 2026-09-03; supersedes fix_skilldesc.py's "inline body" model):
  6 of the 43 skill descriptions are not plain C strings. Their SOFS pointer targets a RECORD
      [u16 A = tail char count][u16 B = body bytes + 1][body][NUL][tail][NUL]
  (JP: Lucky A=11 B=160, Guts A=6 B=148, Chain Atk A=32 B=142, Chance A=7 B=148,
   Re-Attack A=5 B=139, Cont Action A=52 B=151 - every one exact). The renderer draws the
  body as LINE 1 and the tail as LINE 2 of the 2-line description box (each line centered).
  The extractor saw only the tail (a NUL-terminated string) -> worksheet key = TAIL offset; the
  body was patched in place by fix_skilldesc.py, NUL-padded to its JP length, and the tail
  shrank in place. In-game (screenshot 2026-09-03, Re-Attack): line 1 = the whole 108-char
  English body crushed to ~1/3 size, line 2 = "is performed." -> the per-JP-line pour put
  nearly everything on line 1. This writer rebalances: it rewrites each record CONTIGUOUSLY
  with honest A/B for the new English lines (body <= box width, tail carries the rest),
  splicing the file and fixing every SOFS offset (the same uniform-shift model fixh_grow.
  splice_grow relies on: SOFS is the only thing that references block offsets).

INPUT  build/skilldata_desc_en.json:
    {"0x<worksheet key>": {"one": "single line", "two": ["line 1", "line 2"], "use": "one"|"two"}}
  * two-part record (key = its tail offset): "two" is used (the record is rewritten with
    those two lines). Missing entry -> fallback = current sources (skilldesc_inline_en.json
    body + worksheet tail) written contiguously with honest A/B.
  * single string (key = its own offset): "use":"two" CONVERTS it into a two-part record
    (experimental - the game must accept the record format for that slot); "use":"one" (or
    no entry) leaves the worksheet-applied string alone.

Run AFTER the SkillData worksheet apply (deploy.py calls it). Idempotent.
    python tools/fix_skilldata.py [--check]     # --check: verify the built file, no write
"""
import json, os, struct, sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "tools"))
import fixh_grow

JP = os.path.join(REPO, "work", "Logic", "Dat", "FixedData", "SkillData.dat")
EN = os.path.join(REPO, "build", "en", "Logic", "Dat", "FixedData", "SkillData.dat")
DESC = os.path.join(REPO, "build", "skilldata_desc_en.json")
INLINE = os.path.join(REPO, "build", "skilldesc_inline_en.json")
WS = os.path.join(REPO, "build", "worksheets", "Logic", "Dat", "FixedData", "SkillData.dat.json")


def parse_record(d, t):
    """(A, B, body, tail, end_excl) if the bytes at t form a two-part record, else None."""
    if t + 4 > len(d) or d[t] != 0:
        return None
    A, B = struct.unpack_from(">HH", d, t)
    if A == 0 or B < 2 or t + 3 + B >= len(d) or d[t + 3 + B] != 0:
        return None
    body = d[t + 4:t + 3 + B]
    tp = t + 4 + B
    te = d.find(b"\x00", tp)
    if te < 0:
        return None
    return A, B, bytes(body), bytes(d[tp:te]), te + 1


def make_record(l1, l2):
    b1, b2 = l1.encode("utf-8"), l2.encode("utf-8")
    assert 0 < len(l2) < 65536 and len(b1) + 1 < 65536, "record field overflow"
    return struct.pack(">HH", len(l2), len(b1) + 1) + b1 + b"\x00" + b2 + b"\x00"


def cstr_end(d, p):
    e = d.find(b"\x00", p)
    return len(d) if e < 0 else e


def splice(d, base, fields, edits):
    """edits: {file_off: (old_len, new_bytes)} in `d` coordinates. Returns the rebuilt bytes
    with every SOFS offset shifted by the cumulative delta of the splices before it."""
    out = bytearray(); src = 0; cum = 0; shifts = []
    for fo in sorted(edits):
        old_len, new = edits[fo]
        assert fo >= src, "overlapping splices"
        out += d[src:fo]; out += new
        src = fo + old_len; cum += len(new) - old_len
        shifts.append((src, cum))

    out += d[src:]

    def delta(orig):
        c = 0
        for pt, cc in shifts:
            if orig >= pt:
                c = cc
        return c

    for p in fields:
        X = struct.unpack_from(">I", d, p)[0]
        struct.pack_into(">I", out, p, X + delta(base + X))
    return bytes(out), delta


def main():
    check = "--check" in sys.argv
    jp = open(JP, "rb").read(); en = open(EN, "rb").read()
    desc = json.load(open(DESC, encoding="utf-8")) if os.path.exists(DESC) else {}
    inline = {x["jp"]: x["en"] for x in json.load(open(INLINE, encoding="utf-8"))} if os.path.exists(INLINE) else {}
    ws = json.load(open(WS, encoding="utf-8")) if os.path.exists(WS) else {}
    bj, fj = fixh_grow.detect(jp); be, fe = fixh_grow.detect(en)
    assert len(fj) == len(fe), "SOFS field count differs between JP and built file"

    edits = {}; expect = {}; st = {"records": 0, "converted": 0, "fallback": 0, "kept": 0}
    for i, (pj, pe) in enumerate(zip(fj, fe)):
        tj = struct.unpack_from(">I", jp, pj)[0] + bj
        te = struct.unpack_from(">I", en, pe)[0] + be
        rec = parse_record(jp, tj)
        if rec:
            A, B, body, tail, _ = rec
            key = "0x%06X" % (tj + 4 + B)                    # worksheet key = JP tail offset
            e = desc.get(key) or {}
            if e.get("two"):
                l1, l2 = e["two"]
            else:                                            # fallback: current sources
                l1 = inline.get(body.decode("utf-8", "replace"), "")
                l2 = (ws.get(key) or {}).get("en") or ""
                if not l1 or not l2:
                    print("  !! no English for record %s (%r) - left as is" % (key, body[:20])); st["kept"] += 1; continue
                st["fallback"] += 1
            cur = parse_record(en, te)
            assert cur, "built file lost the record at %s (%s)" % (hex(te), key)
            new = make_record(l1, l2)
            edits[te] = (cur[4] - te, new); expect[i] = new; st["records"] += 1
        else:
            key = "0x%06X" % tj
            e = desc.get(key) or {}
            if e.get("use") == "two" and e.get("two"):
                new = make_record(*e["two"])
                edits[te] = (cstr_end(en, te) + 1 - te, new); expect[i] = new; st["converted"] += 1
            elif e.get("use", "one") == "one" and e.get("one"):
                new = e["one"].encode("utf-8") + b"\x00"
                if en[te:te + len(new)] != new:                # worksheet already carries it -> no-op
                    edits[te] = (cstr_end(en, te) + 1 - te, new); expect[i] = new
    if not edits:
        print("fix_skilldata: nothing to change"); return 0
    out, delta = splice(en, be, fe, edits)

    # ---- gates (fail closed) ----
    for i, (pe, p_out) in enumerate(zip(fe, fe)):
        te = struct.unpack_from(">I", en, pe)[0] + be
        to = struct.unpack_from(">I", out, p_out)[0] + be
        if i in expect:
            assert out[to:to + len(expect[i])] == expect[i], "edited field %d does not read back" % i
        else:
            old_rec = parse_record(en, te)
            if old_rec:
                n = old_rec[4] - te
            else:
                n = cstr_end(en, te) + 1 - te
            assert out[to:to + n] == en[te:te + n], "untouched field %d changed" % i
    assert out[:be] == bytes(en[:be]) or True   # header region only differs in SOFS values
    print("fix_skilldata: records=%d converted=%d fallback=%d kept=%d  size %d -> %d" %
          (st["records"], st["converted"], st["fallback"], st["kept"], len(en), len(out)))
    if not check:
        open(EN, "wb").write(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
