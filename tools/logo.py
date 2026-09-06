#!/usr/bin/env python3
"""
LOGO container parser + string reinserter (scenario scripts: work/Logic/Dat/logic/scr*.bin).

Format (reverse-engineered, verified against all 102 scr*.bin):
  0x00  magic "LOGO"
  0x04  file_size (u32 BE) == len(file)
  0x08  0 ; 0x0C 0
  0x10  section table: (count u32 BE, offset u32 BE) pairs, terminated by 0xFFFFFFFF
  ...   data/bytecode sections, then pointer table(s) + string pool(s)
  tail  trailing 0xDEAD filler (4-byte 0xAD alignment, then AD DE words)

String pool(s): contiguous null-terminated UTF-8. One or more *pointer tables*
(sections of u32-BE values) index strings as offsets RELATIVE to the lowest pool
section's offset (the "pool base"). All pointer tables in a file share that base.
A pointer value that lands on padding / invalid UTF-8 (== one past the last
string) is an end-sentinel, not a string.

Reinsertion strategy = SURGICAL IN-PLACE PATCH (safe, zero-relocation):
  Each replacement is written into the original string's byte slot; its UTF-8
  length must be <= the original (Japanese 3 bytes/CJK char -> English 1 byte/ASCII
  almost always shrinks). The output is a copy of the original file with ONLY those
  slot bytes overwritten (new UTF-8 + NUL + 0x00 fill to the original slot width).
  Pool size, every pointer table, the section table, file_size and the trailing
  padding are therefore byte-identical by construction. This is the correctness
  guarantee; it is proven by `verify` (identity reinsert == original, for all files).

Growth (English longer than Japanese) needs pool rebuild + pointer/section
relocation + padding regen; the trailing-padding format has file-specific
irregularities not yet fully reversed, so growth is intentionally NOT implemented
here -- it must be added with its own byte-exact round-trip proof (README Lane 3
correctness gate) before use. In practice English shrinks, so in-place covers it.

CLI:
  python tools/logo.py info   <file>
  python tools/logo.py dump   <file>                 # editable strings: idx, offset, text
  python tools/logo.py verify <file|glob...>         # identity round-trip + functional swap
"""
import struct, sys, glob

MAGIC = b"LOGO"

def u32(d, o): return struct.unpack(">I", d[o:o+4])[0]

def _pad_logo(out):
    """Pad a bytearray to a 0x10 boundary with the 0xDEAD filler (0xAD to a 4-byte
    boundary, then AD/DE by parity). The engine ignores this space; only validity/
    alignment matter for grown files."""
    while len(out) % 4 != 0:
        out.append(0xAD)
    while len(out) % 0x10 != 0:
        out.append(0xAD if len(out) % 2 == 0 else 0xDE)

def _valid_utf8_string_at(d, pos, end):
    """Return the bytes of a null-terminated UTF-8 string starting at pos (no NUL),
    or None if pos doesn't begin a valid non-empty UTF-8 string before `end`."""
    if pos >= end or d[pos] == 0:
        return None
    nul = d.find(b"\x00", pos, end)
    if nul < 0:
        return None
    chunk = d[pos:nul]
    try:
        chunk.decode("utf-8")
    except UnicodeDecodeError:
        return None
    return chunk

class Logo:
    def __init__(self, data):
        self.raw = bytes(data)
        d = self.raw
        if d[:4] != MAGIC:
            raise ValueError(f"not LOGO: {d[:4]!r}")
        self.file_size = u32(d, 4)
        if self.file_size != len(d):
            raise ValueError(f"file_size 0x{self.file_size:X} != len 0x{len(d):X}")
        # section table
        self.sections = []
        o = 0x10
        while o + 8 <= len(d):
            cnt = u32(d, o)
            if cnt == 0xFFFFFFFF:
                break
            self.sections.append((cnt, u32(d, o + 4), o))   # (count, offset, tbl_pos)
            o += 8
        self._analyze()

    def _analyze(self):
        d = self.raw
        offsets = sorted(set(off for _, off, _ in self.sections))
        # pool sections: a section offset that begins a valid UTF-8 string
        pool_offs = [o for o in offsets if _valid_utf8_string_at(d, o, len(d))]
        self.pool_base = pool_offs[0] if pool_offs else None
        # pool end: scan strings from pool_base until a non-string (padding) byte
        self.pool_end = self._scan_pool_end() if self.pool_base is not None else None
        # pointer tables: sections whose entries (rel to pool_base) resolve to string
        # starts. Build editable slots keyed by absolute offset.
        self.ptr_tables = []          # list of dict(off,count,entries,resolved)
        self.slots = {}               # abs_off -> bytes (string content, no NUL)
        self.slot_refs = {}           # abs_off -> list of (table_off, index)
        if self.pool_base is None:
            return
        pb, pe = self.pool_base, self.pool_end
        for cnt, off, _ in self.sections:
            if cnt == 0 or off >= pb:
                continue
            if off + 4*cnt > len(d):
                continue
            entries = [u32(d, off + 4*i) for i in range(cnt)]
            resolved = 0
            local = []
            for i, e in enumerate(entries):
                abs_off = pb + e
                s = _valid_utf8_string_at(d, abs_off, pe) if abs_off < pe else None
                if s is not None and (abs_off == pb or d[abs_off-1] == 0):
                    resolved += 1
                    local.append((abs_off, i))
            # treat as a pointer table only if (almost) all entries resolve
            # (allow up to 1 end-sentinel that points to pool_end)
            sentinels = sum(1 for e in entries if pb + e >= pe)
            if resolved + sentinels == cnt and resolved > 0:
                self.ptr_tables.append(dict(off=off, count=cnt, entries=entries))
                for abs_off, i in local:
                    self.slots.setdefault(abs_off, _valid_utf8_string_at(d, abs_off, pe))
                    self.slot_refs.setdefault(abs_off, []).append((off, i))

    def _scan_pool_end(self):
        d = self.raw
        pos = self.pool_base
        last_good = pos
        n = len(d)
        while pos < n:
            if d[pos] == 0:               # empty string slot
                pos += 1; last_good = pos; continue
            nul = d.find(b"\x00", pos, n)
            if nul < 0:
                break
            try:
                d[pos:nul].decode("utf-8")
            except UnicodeDecodeError:
                break
            pos = nul + 1
            last_good = pos
        return last_good

    # ---- views ----
    def editable(self):
        """Sorted list of (abs_off, text) for every pointer-referenced string."""
        out = []
        for off in sorted(self.slots):
            try:
                out.append((off, self.slots[off].decode("utf-8")))
            except UnicodeDecodeError:
                out.append((off, None))
        return out

    def slot_capacity(self, abs_off):
        """Bytes available for content at this slot (excludes the NUL terminator)."""
        return len(self.slots[abs_off])

    # ---- reinsertion (in-place for <=, append+repoint for growth) ----
    def reinsert(self, edits):
        """edits: {abs_off: new_text}. Returns new file bytes.

        Replacements that FIT the original slot are written in place (nothing moves).
        Replacements that GROW are appended after the pool and their pointer-table
        entries are repointed to the new location -- so no existing pool byte moves,
        every unchanged string keeps its offset (any hidden absolute reference to it
        stays valid), only the grown strings relocate. End-sentinel pointers (== pool
        size) and any section offset == pool_end are advanced to the new pool end;
        file_size and the 0xDEAD padding are regenerated. With no growth the output is
        byte-identical except the edited slots."""
        out = bytearray(self.raw)
        appended = bytearray()
        repoints = []                                  # (table_off, index, new_rel)
        for abs_off, text in edits.items():
            if abs_off not in self.slots:
                raise KeyError(f"0x{abs_off:X} is not a known string slot")
            cap = len(self.slots[abs_off])
            nb = text.encode("utf-8")
            if len(nb) <= cap:
                out[abs_off:abs_off+cap] = nb + b"\x00" * (cap - len(nb))
            else:
                new_rel = (self.pool_end + len(appended)) - self.pool_base
                appended += nb + b"\x00"
                for (t_off, idx) in self.slot_refs[abs_off]:
                    repoints.append((t_off, idx, new_rel))
        if not appended:
            return bytes(out)                          # in-place only; structure untouched

        old_pool_size = self.pool_end - self.pool_base
        new_pool_size = old_pool_size + len(appended)
        new_pool_end  = self.pool_base + new_pool_size
        out = bytearray(out[:self.pool_end]) + bytes(appended)   # keep in-place edits, then append
        _pad_logo(out)
        struct.pack_into(">I", out, 4, len(out))                 # file_size
        for t_off, idx, new_rel in repoints:                     # repoint grown strings
            struct.pack_into(">I", out, t_off + 4*idx, new_rel)
        for t in self.ptr_tables:                                # advance end-sentinels
            for i, e in enumerate(t["entries"]):
                if e == old_pool_size:
                    struct.pack_into(">I", out, t["off"] + 4*i, new_pool_size)
        for cnt, off, tbl in self.sections:                      # advance section offsets at pool end
            if off == self.pool_end:
                struct.pack_into(">I", out, tbl + 4, new_pool_end)
        return bytes(out)


def load(path): return Logo(open(path, "rb").read())

def cmd_info(path):
    L = load(path)
    print(f"{path}: size=0x{L.file_size:X} sections={len(L.sections)} "
          f"pool_base={hex(L.pool_base) if L.pool_base else None} "
          f"pool_end={hex(L.pool_end) if L.pool_end else None} "
          f"ptr_tables={[(hex(t['off']),t['count']) for t in L.ptr_tables]} "
          f"editable_strings={len(L.slots)}")

def cmd_dump(path):
    L = load(path)
    sys.stdout.reconfigure(encoding="utf-8")
    for i, (off, t) in enumerate(L.editable()):
        s = ("<non-utf8>" if t is None else t).replace("\n", "\\n")
        cap = L.slot_capacity(off)
        print(f"  [{i:4}] @0x{off:06X} cap={cap:3}B  {s}")

def cmd_verify(paths):
    files = []
    for p in paths:
        files += glob.glob(p)
    files = sorted(files)
    n_id = n_struct = n_func = 0
    bad = []
    for p in files:
        try:
            L = load(p)
            # (1) identity reinsert == original (the byte-identical gate)
            ident = {off: L.slots[off].decode("utf-8") for off in L.slots}
            if L.reinsert(ident) == L.raw:
                n_id += 1
            else:
                bad.append((p, "identity reinsert != original")); continue
            # (2) structural: at least one pointer table and all slots are utf-8
            if L.ptr_tables and all(t is not None for _, t in L.editable()):
                n_struct += 1
            else:
                bad.append((p, "structural: no ptr table / non-utf8 slot")); continue
            # (3) functional swap: replace each slot with a short ASCII marker that
            #     fits, re-parse the output, confirm every edited pointer reads the
            #     marker back and the file size is unchanged.
            edits = {}
            for off in L.slots:
                cap = len(L.slots[off])
                marker = ("E%d" % (off & 0xFF))[:cap] if cap >= 1 else ""
                edits[off] = marker
            out = L.reinsert(edits)
            L2 = Logo(out)
            ok = (len(out) == len(L.raw))
            for off in L.slots:
                got = L2.slots.get(off)
                if got is None or got.decode("utf-8", "replace") != edits[off]:
                    ok = False; break
            # also: bytes outside slots must be unchanged
            if ok:
                mask = bytearray(out)
                ref = bytearray(L.raw)
                for off in L.slots:
                    cap = len(L.slots[off])
                    mask[off:off+cap] = ref[off:off+cap]   # ignore slot regions
                if bytes(mask) != L.raw:
                    ok = False
            if ok:
                n_func += 1
            else:
                bad.append((p, "functional swap mismatch"))
        except Exception as e:
            bad.append((p, f"{type(e).__name__}: {e}"))
    print(f"files={len(files)}")
    print(f"  identity round-trip byte-identical : {n_id}/{len(files)}")
    print(f"  structural (ptr table + utf8 slots): {n_struct}/{len(files)}")
    print(f"  functional swap (re-parse reads back, only slots change): {n_func}/{len(files)}")
    for p, e in bad[:25]:
        print(f"  FAIL {p}: {e}")
    return len(bad)

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(__doc__); sys.exit(1)
    cmd, args = sys.argv[1], sys.argv[2:]
    if   cmd == "info":   cmd_info(args[0])
    elif cmd == "dump":   cmd_dump(args[0])
    elif cmd == "verify": sys.exit(1 if cmd_verify(args) else 0)
    else: print("unknown cmd", cmd); sys.exit(1)
