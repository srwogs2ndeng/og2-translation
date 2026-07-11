#!/usr/bin/env python3
# Scan a binary for Shift-JIS text runs and report offsets + decoded text.
import sys

def is_sjis_lead(b):  # double-byte lead
    return (0x81 <= b <= 0x9F) or (0xE0 <= b <= 0xEF)
def is_sjis_trail(b):
    return (0x40 <= b <= 0x7E) or (0x80 <= b <= 0xFC)
def is_halfkana(b):
    return 0xA1 <= b <= 0xDF
def is_ascii_print(b):
    return 0x20 <= b <= 0x7E

data = open(sys.argv[1], "rb").read()
min_run = int(sys.argv[2]) if len(sys.argv) > 2 else 4
limit   = int(sys.argv[3]) if len(sys.argv) > 3 else 40

runs = []
i = 0
n = len(data)
while i < n:
    start = i
    chars = 0
    buf = bytearray()
    while i < n:
        b = data[i]
        if is_sjis_lead(b) and i+1 < n and is_sjis_trail(data[i+1]):
            buf += data[i:i+2]; i += 2; chars += 1
        elif is_halfkana(b) or is_ascii_print(b):
            buf += data[i:i+1]; i += 1; chars += 1
        else:
            break
    # reject low-variety filler (e.g. repeated 0xDEAD) — need several distinct byte pairs
    distinct = len(set(bytes(buf[k:k+2]) for k in range(0, len(buf)-1, 2)))
    if chars >= min_run and any(c > 0x7E for c in buf) and distinct >= 3:  # require some JP + variety
        try: txt = buf.decode("shift_jis")
        except Exception: txt = buf.decode("shift_jis", "replace")
        runs.append((start, len(buf), txt))
    if i == start:  # no progress -> skip this byte
        i += 1

print(f"{len(runs)} Shift-JIS runs (>= {min_run} chars). Showing first {limit}:")
for off, ln, txt in runs[:limit]:
    print(f"  0x{off:06X} [{ln:3}] {txt}")
print(f"... total runs: {len(runs)}")
