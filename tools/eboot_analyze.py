#!/usr/bin/env python3
# Minimal Ghidra-lite for the decrypted PPC64 EBOOT: disassemble, detect functions,
# build call + data xrefs, and search. Goal: find the dialogue glyph-advance.
import struct, re, sys
from capstone import *

EL = r'games/BLJS10133_EN/PS3_GAME/USRDIR/EBOOT.elf'
d = open(EL, 'rb').read()
phoff = struct.unpack('>Q', d[0x20:0x28])[0]; phnum = struct.unpack('>H', d[0x38:0x3A])[0]; phe = struct.unpack('>H', d[0x36:0x38])[0]
SEGS = []
for i in range(phnum):
    p = d[phoff+i*phe:phoff+(i+1)*phe]
    t = struct.unpack('>I', p[0:4])[0]; fl = struct.unpack('>I', p[4:8])[0]
    off = struct.unpack('>Q', p[8:16])[0]; va = struct.unpack('>Q', p[16:24])[0]; fsz = struct.unpack('>Q', p[32:40])[0]
    if t == 1 and fsz: SEGS.append((off, va, fsz, fl))
# main code seg
CODE = SEGS[0]  # off=0, va=0x10000
COFF, CVA, CSZ, _ = CODE
code = d[COFF:COFF+CSZ]
def va2off(va): return COFF + (va - CVA)
def off2va(off): return CVA + (off - COFF)
def word(va): return struct.unpack('>I', d[va2off(va):va2off(va)+4])[0]

md = Cs(CS_ARCH_PPC, CS_MODE_64 | CS_MODE_BIG_ENDIAN); md.detail = False

def disasm(va, n):
    out = []
    for ins in md.disasm(d[va2off(va):va2off(va)+n*4], va):
        out.append((ins.address, ins.mnemonic, ins.op_str));
        if len(out) >= n: break
    return out

def search_bytes(pat_re):
    """4-aligned regex over the code segment. Returns list of vaddr."""
    return [CVA + m.start() for m in re.finditer(pat_re, code) if m.start() % 4 == 0]

if __name__ == '__main__':
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'stats'
    if cmd == 'stats':
        # count cmpwi/cmplwi rA, 0x40  ('@' newline?) and to 0x3000 handling
        for name, pat in [("cmpwi *,0x40 ('@')", rb'\x2c[\x00-\x1f]\x00\x40'),
                          ("cmplwi *,0x40",       rb'\x28[\x00-\x1f]\x00\x40'),
                          ("cmpwi *,0x0a (LF)",   rb'\x2c[\x00-\x1f]\x00\x0a'),
                          ("li *,0x20 (fw adv?)", rb'\x38[\x00-\x1f]\x00\x20')]:
            hits = search_bytes(pat)
            print(f'{name}: {len(hits)} hits')
        print('code seg vaddr 0x%X..0x%X (%.1f MB)' % (CVA, CVA+CSZ, CSZ/1e6))
    elif cmd == 'dis':
        va = int(sys.argv[2], 16); n = int(sys.argv[3]) if len(sys.argv) > 3 else 20
        for a, m, o in disasm(va, n): print(f'  0x{a:08X}: {m} {o}')
