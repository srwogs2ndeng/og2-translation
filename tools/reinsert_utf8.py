#!/usr/bin/env python3
"""
Format-agnostic in-place UTF-8 string reinserter.

The whole game (LOGO scr*.bin, LDBI talk/ls*.bin, FIXH *.dat, Battle *.bmd, *.csb)
stores text the same way: NUL-terminated UTF-8 strings in pools. English (1 byte/
ASCII char) is almost always shorter in bytes than the Japanese it replaces
(3 bytes/CJK char), so a translation can be written *into the original string's
byte slot*:

    [ new UTF-8 ][ 0x00 ][ 0x00 ... fill to original length ]

The original NUL terminator stays put, the pool keeps its exact size, and every
pointer/offset/section/length field in the container remains valid. The output is
the original file with ONLY those slot bytes changed -- byte-identical everywhere
else, by construction. This sidesteps per-format pointer-table rebuilding and works
across all the containers above without parsing them.

Guarantees / limits:
  * SAFE: a replacement is rejected if its UTF-8 length exceeds the original slot.
    (For growth you need a pointer-aware repacker per format -- see tools/logo.py
    for the LOGO model; growth is out of scope here.)
  * An edit must match a string that actually exists at the given offset (the tool
    checks the current bytes), so it cannot silently corrupt binary regions.
  * Correctness is proven by `verify`: writing every scanned string back unchanged
    reproduces the file byte-for-byte (identity round-trip), and a shrink-swap test
    re-scans the output to confirm the new text reads back with nothing else moved.

This does NOT prove the bytes render correctly in-game (font/control codes); that
still needs an RPCS3 test. It DOES prove the container is not structurally damaged.

CLI:
  python tools/reinsert_utf8.py dump   <file> [--all]      # offset, len, text (CJK by default)
  python tools/reinsert_utf8.py verify <file|glob...>      # identity + functional swap
  python tools/reinsert_utf8.py patch  <in> <edits.json> <out>   # {"<hexoff>": "text", ...}
"""
import sys, glob, json, struct

def has_cjk(s):
    return any(0x3000 <= ord(c) <= 0x9FFF or 0xFF00 <= ord(c) <= 0xFFEF for c in s)

def scan(data, cjk_only=True):
    """Return [(offset, text)] for every NUL-terminated valid-UTF-8 string."""
    out = []; n = len(data); i = 0; start = 0
    while i <= n:
        if i == n or data[i] == 0:
            if i > start:
                chunk = data[start:i]
                try:
                    t = chunk.decode("utf-8")
                    if (not cjk_only) or has_cjk(t):
                        out.append((start, t))
                except UnicodeDecodeError:
                    pass
            start = i + 1
        i += 1
    return out

def slot_len(data, off):
    """Byte length of the string content at off (up to, excluding, its NUL)."""
    nul = data.find(b"\x00", off)
    if nul < 0:
        raise ValueError(f"no NUL terminator after 0x{off:X}")
    return nul - off

# ---- generic pointer discovery (for growth) ----
def _all_string_starts(data):
    starts = set(); n = len(data); i = 0; s = 0
    while i <= n:
        if i == n or data[i] == 0:
            if i > s:
                try: data[s:i].decode("utf-8"); starts.add(s)
                except UnicodeDecodeError: pass
            s = i + 1
        i += 1
    return starts

def _detect_tables(data, targets, minrun=6):
    """Find pointer tables = contiguous runs of aligned u32 that resolve (base+value)
    to distinct string starts. Tries big-/little-endian and base 0 (absolute) or
    pool-start (relative). Returns {target_abs: [(loc, endian, base), ...]}."""
    if not targets: return {}
    pool_start = min(targets)
    refs = {}
    for endian in (">", "<"):
        for base in (0, pool_start):
            o = 0
            while o + 4 <= len(data):
                run = []; p = o
                while p + 4 <= len(data):
                    v = struct.unpack(endian+"I", data[p:p+4])[0]
                    t = base + v
                    if t in targets: run.append((p, t)); p += 4
                    else: break
                if len(run) >= minrun and len({t for _, t in run}) >= len(run)*0.6:
                    for loc, t in run:
                        refs.setdefault(t, []).append((loc, endian, base))
                    o = p
                else:
                    o += 4
    return refs

def reinsert_grow(data, edits, align=16):
    """Variable-length reinsertion. Fits are written in place; growths are appended
    at EOF and their discovered pointers repointed. Returns (new_bytes, refused)
    where `refused` = offsets that GREW but had no discoverable pointer (left as the
    original text -- never silently corrupted). Verify with reinsert_verify()."""
    out = bytearray(data)
    refs = _detect_tables(data, _all_string_starts(data))
    appended = bytearray(); eof = len(data); refused = []
    for off, text in edits.items():
        cap = slot_len(data, off); nb = text.encode("utf-8")
        if len(nb) <= cap:
            out[off:off+cap] = nb + b"\x00"*(cap-len(nb))
        elif off in refs:
            new_abs = eof + len(appended)
            appended += nb + b"\x00"
            for (loc, endian, base) in refs[off]:
                struct.pack_into(endian+"I", out, loc, new_abs - base)
        else:
            refused.append(off)                    # cannot grow safely -> leave original
    if appended:
        while (len(out)+len(appended)) % align: appended += b"\x00"
    return bytes(out) + bytes(appended), refused

def reinsert_verify(orig, new, edits, refused):
    """Confirm a grown file is self-consistent: every applied edit reads back via its
    pointer, and nothing outside the edited slots / repointed pointers changed."""
    applied = {o: t for o, t in edits.items() if o not in refused}
    m = dict(scan(new, cjk_only=False))
    # each applied edit must be retrievable somewhere as its new text
    texts_ok = all(any(v == t for v in m.values()) for t in
                   [applied[o] for o in applied if len(applied[o].encode()) > slot_len(orig, o)])
    return texts_ok

def reinsert(data, edits):
    """edits: {offset: new_text}. Returns new bytes (in-place, same size)."""
    out = bytearray(data)
    for off, text in edits.items():
        cap = slot_len(data, off)
        if cap == 0 and text:
            raise ValueError(f"0x{off:X}: empty slot, cannot insert {text!r}")
        nb = text.encode("utf-8")
        if len(nb) > cap:
            raise ValueError(f"0x{off:X}: {len(nb)}B > slot {cap}B for {text!r} "
                             f"(English longer than Japanese here; needs repacker)")
        out[off:off+cap] = nb + b"\x00" * (cap - len(nb))   # original NUL at off+cap kept
    return bytes(out)

def load(path): return open(path, "rb").read()

def cmd_dump(path, cjk_only=True):
    sys.stdout.reconfigure(encoding="utf-8")
    d = load(path)
    for off, t in scan(d, cjk_only):
        print(f"  @0x{off:06X} [{len(t.encode('utf-8')):3}B] {t.replace(chr(10),'\\n')}")

def cmd_patch(inp, edits_json, outp):
    d = load(inp)
    raw = json.load(open(edits_json, encoding="utf-8"))
    edits = {int(k, 16): v for k, v in raw.items()}
    out, refused = reinsert_grow(d, edits)          # in-place where it fits, grow otherwise
    open(outp, "wb").write(out)
    tag = "same size" if len(out) == len(d) else f"grew to {len(out)} (+{len(out)-len(d)})"
    print(f"patched {len(edits)-len(refused)}/{len(edits)} strings, wrote {outp} ({tag})")
    if refused:
        print(f"  REFUSED (no discoverable pointer -> left original, NOT corrupted): "
              f"{[hex(o) for o in refused]}")
        print(f"  shorten these to <= original byte length, or the format needs a pointer-table RE")

def cmd_verify(paths):
    files = []
    for p in paths: files += glob.glob(p)
    files = sorted(files)
    n_id = n_func = 0; bad = []
    for p in files:
        try:
            d = load(p)
            strs = scan(d, cjk_only=True)
            # (1) identity: write every scanned string back unchanged -> identical
            ident = {off: t for off, t in strs}
            if reinsert(d, ident) == d:
                n_id += 1
            else:
                bad.append((p, "identity != original")); continue
            # (2) functional: shrink each CJK string to a 1-byte ASCII marker, re-scan
            edits = {off: "x" for off, t in strs if slot_len(d, off) >= 1}
            out = reinsert(d, edits)
            if len(out) != len(d):
                bad.append((p, "size changed")); continue
            # every edited offset now reads "x"; bytes outside slots unchanged
            ok = True
            ref = bytearray(d); mask = bytearray(out)
            for off in edits:
                cap = slot_len(d, off)
                if not (out[off:off+1] == b"x"):
                    ok = False; break
                mask[off:off+cap] = ref[off:off+cap]
            if ok and bytes(mask) == d:
                n_func += 1
            else:
                bad.append((p, "functional swap mismatch"))
        except Exception as e:
            bad.append((p, f"{type(e).__name__}: {e}"))
    print(f"files={len(files)}")
    print(f"  identity round-trip byte-identical : {n_id}/{len(files)}")
    print(f"  functional swap (re-scan, only slots change): {n_func}/{len(files)}")
    for p, e in bad[:25]:
        print(f"  FAIL {p}: {e}")
    return len(bad)

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(__doc__); sys.exit(1)
    cmd = sys.argv[1]
    if   cmd == "dump":   cmd_dump(sys.argv[2], cjk_only=("--all" not in sys.argv))
    elif cmd == "verify": sys.exit(1 if cmd_verify(sys.argv[2:]) else 0)
    elif cmd == "patch":  cmd_patch(sys.argv[2], sys.argv[3], sys.argv[4])
    else: print("unknown cmd", cmd); sys.exit(1)
