#!/usr/bin/env python3
# Scan for null-terminated UTF-8 strings containing CJK characters.
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

data = open(sys.argv[1], "rb").read()
min_cjk = int(sys.argv[2]) if len(sys.argv) > 2 else 1
limit   = int(sys.argv[3]) if len(sys.argv) > 3 else 60

def has_cjk(s):
    return any(0x3000 <= ord(c) <= 0x9FFF or 0xFF00 <= ord(c) <= 0xFFEF for c in s)
def cjk_count(s):
    return sum(1 for c in s if 0x3040 <= ord(c) <= 0x9FFF)

strings = []
i, n = 0, len(data)
start = 0
while i <= n:
    if i == n or data[i] == 0:
        if i > start:
            chunk = data[start:i]
            try:
                s = chunk.decode("utf-8")
                if has_cjk(s) and len(s) >= 1:
                    strings.append((start, s))
            except UnicodeDecodeError:
                pass
        start = i + 1
    i += 1

dialogue = [(o, s) for o, s in strings if cjk_count(s) >= min_cjk]
print(f"{len(strings)} CJK UTF-8 strings total; {len(dialogue)} with >={min_cjk} kana/kanji. First {limit}:")
for off, s in dialogue[:limit]:
    s1 = s.replace("\n", "\\n")
    print(f"  0x{off:06X} [{len(s):3}] {s1}")
