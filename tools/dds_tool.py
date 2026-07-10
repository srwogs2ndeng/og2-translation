#!/usr/bin/env python3
"""
DDS <-> PNG batch converter for UI-texture translation (pure Python, no deps).

The PS3 2nd OG UI is graphics: ~550 .dds in Common (menu labels, scene titles,
tutorial headers). Editing them = redraw in a normal image editor. This tool exports
DDS to PNG for editing and re-imports edited PNGs into DDS *in the same format and
byte size*, so the result drops straight into the repacker pipeline (pack_psarc ->
encrypt_sdat -> iso_patch) with an exact fit.

Formats seen in Common: 542 uncompressed A8R8G8B8 (32bpp, no mips) -- these round-trip
BYTE-IDENTICAL (lossless). 10 are DXT1/3/5 (logos, a few scene titles) -- decoded for
export; DXT1/DXT5 re-encoded on import (lossy, same size). The UI-critical dirs
(Option, SceneTitle, LessonTitle) are uncompressed.

CLI:
  python tools/dds_tool.py export      <in.dds> <out.png>
  python tools/dds_tool.py apply       <in.png> <target.dds> [--out o.dds]   # header from target
  python tools/dds_tool.py export-tree <ddsroot> <pngroot>
  python tools/dds_tool.py apply-tree  <pngroot> <ddsroot>                    # overwrite DDS in place
  python tools/dds_tool.py verify      <in.dds | glob...>                     # export->apply round-trip
"""
import struct, sys, zlib, glob, os

# ---------------- PNG (8-bit truecolor / truecolor+alpha) ----------------
def png_write(path, w, h, rgba):
    def chunk(tag, data):
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag+data) & 0xFFFFFFFF)
    raw = bytearray()
    for y in range(h):
        raw.append(0)                                   # filter: none
        raw += rgba[y*w*4:(y+1)*w*4]
    out = b"\x89PNG\r\n\x1a\n"
    out += chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0))
    out += chunk(b"IDAT", zlib.compress(bytes(raw), 9))
    out += chunk(b"IEND", b"")
    open(path, "wb").write(out)

def _paeth(a, b, c):
    p = a + b - c; pa = abs(p-a); pb = abs(p-b); pc = abs(p-c)
    return a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)

def png_read(path):
    d = open(path, "rb").read()
    assert d[:8] == b"\x89PNG\r\n\x1a\n", "not a PNG"
    i = 8; w = h = bd = ct = il = None; idat = bytearray()
    while i < len(d):
        ln = struct.unpack(">I", d[i:i+4])[0]; tag = d[i+4:i+8]; data = d[i+8:i+8+ln]; i += 12+ln
        if tag == b"IHDR":
            w, h, bd, ct, _, _, il = struct.unpack(">IIBBBBB", data)
        elif tag == b"IDAT":
            idat += data
        elif tag == b"IEND":
            break
    assert bd == 8 and il == 0 and ct in (2, 6), f"unsupported PNG (bd={bd} ct={ct} il={il}); export 8-bit RGB/RGBA non-interlaced"
    ch = 4 if ct == 6 else 3
    raw = zlib.decompress(bytes(idat))
    stride = w*ch
    out = bytearray(h*stride); prev = bytearray(stride); pos = 0
    for y in range(h):
        ft = raw[pos]; pos += 1
        line = bytearray(raw[pos:pos+stride]); pos += stride
        if ft == 1:
            for x in range(ch, stride): line[x] = (line[x] + line[x-ch]) & 0xFF
        elif ft == 2:
            for x in range(stride): line[x] = (line[x] + prev[x]) & 0xFF
        elif ft == 3:
            for x in range(stride):
                a = line[x-ch] if x >= ch else 0
                line[x] = (line[x] + ((a + prev[x]) >> 1)) & 0xFF
        elif ft == 4:
            for x in range(stride):
                a = line[x-ch] if x >= ch else 0; c = prev[x-ch] if x >= ch else 0
                line[x] = (line[x] + _paeth(a, prev[x], c)) & 0xFF
        out[y*stride:(y+1)*stride] = line; prev = line
    # to RGBA
    if ch == 4:
        return w, h, bytes(out)
    rgba = bytearray(w*h*4)
    for p in range(w*h):
        rgba[p*4:p*4+3] = out[p*3:p*3+3]; rgba[p*4+3] = 255
    return w, h, bytes(rgba)

# ---------------- DDS header ----------------
class DDS:
    def __init__(self, raw):
        assert raw[:4] == b"DDS ", "not DDS"
        self.raw = raw
        self.h = struct.unpack("<I", raw[12:16])[0]
        self.w = struct.unpack("<I", raw[16:20])[0]
        self.mips = struct.unpack("<I", raw[28:32])[0]
        self.pf_flags = struct.unpack("<I", raw[0x50:0x54])[0]
        self.fourcc = raw[0x54:0x58]
        self.bits = struct.unpack("<I", raw[0x58:0x5C])[0]
        self.rm, self.gm, self.bm, self.am = struct.unpack("<IIII", raw[0x5C:0x6C])
        self.header = raw[:0x80]
        self.data = raw[0x80:]
    def compressed(self): return self.fourcc in (b"DXT1", b"DXT3", b"DXT5")

def _shift(mask):
    if mask == 0: return 0, 0
    s = 0
    while not (mask >> s) & 1: s += 1
    bits = 0; m = mask >> s
    while (m >> bits) & 1: bits += 1
    return s, bits

# ---------------- uncompressed <-> RGBA ----------------
def _unc_to_rgba(dds):
    w, h, data = dds.w, dds.h, dds.data
    bpp = dds.bits // 8
    rs, rb = _shift(dds.rm); gs, gb = _shift(dds.gm); bs, bb = _shift(dds.bm); as_, ab = _shift(dds.am)
    out = bytearray(w*h*4)
    for p in range(w*h):
        px = int.from_bytes(data[p*bpp:p*bpp+bpp], "little")
        r = (px & dds.rm) >> rs; g = (px & dds.gm) >> gs; b = (px & dds.bm) >> bs
        a = ((px & dds.am) >> as_) if dds.am else (1 << (ab or 8)) - 1
        # scale to 8-bit
        out[p*4+0] = (r*255)//((1<<rb)-1) if rb else 0
        out[p*4+1] = (g*255)//((1<<gb)-1) if gb else 0
        out[p*4+2] = (b*255)//((1<<bb)-1) if bb else 0
        out[p*4+3] = (a*255)//((1<<ab)-1) if ab else 255
    return bytes(out)

def _rgba_to_unc(dds, rgba):
    w, h = dds.w, dds.h; bpp = dds.bits // 8; orig = dds.data
    rs, rb = _shift(dds.rm); gs, gb = _shift(dds.gm); bs, bb = _shift(dds.bm); as_, ab = _shift(dds.am)
    covered = dds.rm | dds.gm | dds.bm | dds.am
    out = bytearray(w*h*bpp)
    for p in range(w*h):
        r, g, b, a = rgba[p*4:p*4+4]
        base = int.from_bytes(orig[p*bpp:p*bpp+bpp], "little") if len(orig) >= (p+1)*bpp else 0
        px = base & ~covered                       # preserve unused/padding bits (e.g. X in X8R8G8B8)
        if rb: px |= ((r*((1<<rb)-1))//255) << rs
        if gb: px |= ((g*((1<<gb)-1))//255) << gs
        if bb: px |= ((b*((1<<bb)-1))//255) << bs
        if ab: px |= ((a*((1<<ab)-1))//255) << as_
        out[p*bpp:p*bpp+bpp] = px.to_bytes(bpp, "little")
    return bytes(out)

# ---------------- DXT (BC1/BC3) ----------------
def _c565(c):
    r = ((c >> 11) & 0x1F); g = ((c >> 5) & 0x3F); b = c & 0x1F
    return (r*255)//31, (g*255)//63, (b*255)//31

def _to565(r, g, b):
    return ((r >> 3) << 11) | ((g >> 2) << 5) | (b >> 3)

def _dxt_decode(dds):
    w, h, data = dds.w, dds.h, dds.data
    out = bytearray(w*h*4); bx = (w+3)//4; by = (h+3)//4; off = 0
    dxt5 = dds.fourcc == b"DXT5"; dxt3 = dds.fourcc == b"DXT3"
    for cy in range(by):
        for cx in range(bx):
            alpha = [255]*16
            if dxt5:
                a0, a1 = data[off], data[off+1]; bits = int.from_bytes(data[off+2:off+8], "little"); off += 8
                at = [a0, a1]
                if a0 > a1: at += [((8-i)*a0+i*a1)//7 for i in range(1, 7)]
                else: at += [((6-i)*a0+i*a1)//5 for i in range(1, 5)] + [0, 255]
                for i in range(16): alpha[i] = at[(bits >> (3*i)) & 7]
            elif dxt3:
                ab = int.from_bytes(data[off:off+8], "little"); off += 8
                for i in range(16): alpha[i] = ((ab >> (4*i)) & 0xF)*17
            c0, c1 = struct.unpack("<HH", data[off:off+4]); idx = int.from_bytes(data[off+4:off+8], "little"); off += 8
            r0, g0, b0 = _c565(c0); r1, g1, b1 = _c565(c1)
            col = [(r0, g0, b0), (r1, g1, b1)]
            if c0 > c1 or dxt5 or dxt3:
                col.append(((2*r0+r1)//3, (2*g0+g1)//3, (2*b0+b1)//3))
                col.append(((r0+2*r1)//3, (g0+2*g1)//3, (b0+2*b1)//3))
            else:
                col.append(((r0+r1)//2, (g0+g1)//2, (b0+b1)//2)); col.append((0, 0, 0))
            for i in range(16):
                px, py = cx*4 + (i % 4), cy*4 + (i//4)
                if px >= w or py >= h: continue
                r, g, b = col[(idx >> (2*i)) & 3]; o = (py*w+px)*4
                out[o:o+4] = bytes((r, g, b, alpha[i]))
    return bytes(out)

def _block_rgba(rgba, w, h, cx, cy):
    px = []
    for i in range(16):
        x = min(cx*4 + i % 4, w-1); y = min(cy*4 + i//4, h-1)
        px.append(tuple(rgba[(y*w+x)*4:(y*w+x)*4+4]))
    return px

def _dxt_encode(dds, rgba):
    w, h = dds.w, dds.h; bx = (w+3)//4; by = (h+3)//4; out = bytearray()
    dxt5 = dds.fourcc == b"DXT5"; dxt3 = dds.fourcc == b"DXT3"
    for cy in range(by):
        for cx in range(bx):
            blk = _block_rgba(rgba, w, h, cx, cy)
            if dxt5:
                a = [p[3] for p in blk]; a0, a1 = max(a), min(a)
                if a0 == a1: a1 = max(0, a0-1)
                at = [a0, a1] + [((8-i)*a0+i*a1)//7 for i in range(1, 7)]
                bits = 0
                for i, av in enumerate(a):
                    bi = min(range(8), key=lambda k: abs(at[k]-av)); bits |= bi << (3*i)
                out += bytes((a0, a1)) + bits.to_bytes(6, "little")
            elif dxt3:
                ab = 0
                for i, p in enumerate(blk): ab |= (p[3]//17) << (4*i)
                out += ab.to_bytes(8, "little")
            # color: bounding-box endpoints
            rs = [p[0] for p in blk]; gs = [p[1] for p in blk]; bs = [p[2] for p in blk]
            cmax = _to565(max(rs), max(gs), max(bs)); cmin = _to565(min(rs), min(gs), min(bs))
            if cmax < cmin: cmax, cmin = cmin, cmax
            if cmax == cmin: cmin = max(0, cmax-1)  # ensure 4-color mode (c0>c1)
            r0, g0, b0 = _c565(cmax); r1, g1, b1 = _c565(cmin)
            pal = [(r0, g0, b0), (r1, g1, b1), ((2*r0+r1)//3, (2*g0+g1)//3, (2*b0+b1)//3), ((r0+2*r1)//3, (g0+2*g1)//3, (b0+2*b1)//3)]
            idx = 0
            for i, p in enumerate(blk):
                bi = min(range(4), key=lambda k: (pal[k][0]-p[0])**2+(pal[k][1]-p[1])**2+(pal[k][2]-p[2])**2)
                idx |= bi << (2*i)
            out += struct.pack("<HH", cmax, cmin) + idx.to_bytes(4, "little")
    return bytes(out)

# ---------------- top-level ----------------
def to_rgba(dds):
    return _dxt_decode(dds) if dds.compressed() else _unc_to_rgba(dds)

def from_rgba(dds, rgba):
    """New DDS bytes = original header + re-encoded top-mip pixels. Same size as
    long as dimensions/format match (mips>1 not regenerated -- Common has mips=0)."""
    body = _dxt_encode(dds, rgba) if dds.compressed() else _rgba_to_unc(dds, rgba)
    if dds.mips and dds.mips > 1:
        raise NotImplementedError("mipmapped DDS not supported (Common textures have none)")
    return dds.header + body

def cmd_export(dds_path, png_path):
    dds = DDS(open(dds_path, "rb").read())
    png_write(png_path, dds.w, dds.h, to_rgba(dds))
    print(f"{dds_path} -> {png_path} ({dds.w}x{dds.h}, {dds.fourcc if dds.compressed() else 'RGBA'})")

def cmd_apply(png_path, dds_path, out=None):
    dds = DDS(open(dds_path, "rb").read())
    w, h, rgba = png_read(png_path)
    if (w, h) != (dds.w, dds.h):
        raise ValueError(f"dimension mismatch: png {w}x{h} vs dds {dds.w}x{dds.h} (keep same size)")
    new = from_rgba(dds, rgba)
    if len(new) != len(dds.raw):
        raise ValueError(f"size changed {len(dds.raw)} -> {len(new)} (unexpected)")
    open(out or dds_path, "wb").write(new)
    print(f"{png_path} -> {out or dds_path} ({len(new)} bytes)")

def cmd_export_tree(ddsroot, pngroot):
    n = 0
    for p in glob.glob(os.path.join(ddsroot, "**", "*.dds"), recursive=True):
        rel = os.path.relpath(p, ddsroot); dst = os.path.join(pngroot, rel[:-4]+".png")
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        try: cmd_export(p, dst); n += 1
        except Exception as e: print(f"  SKIP {p}: {e}")
    print(f"exported {n} textures")

def cmd_apply_tree(pngroot, ddsroot):
    n = 0
    for p in glob.glob(os.path.join(pngroot, "**", "*.png"), recursive=True):
        rel = os.path.relpath(p, pngroot); tgt = os.path.join(ddsroot, rel[:-4]+".dds")
        if not os.path.exists(tgt): print(f"  no target for {rel}"); continue
        try: cmd_apply(p, tgt); n += 1
        except Exception as e: print(f"  SKIP {p}: {e}")
    print(f"applied {n} textures")

def cmd_verify(paths):
    import tempfile
    files = []
    for p in paths: files += glob.glob(p, recursive=True)
    exact = lossy = bad = 0
    for p in sorted(files):
        try:
            dds = DDS(open(p, "rb").read())
            rgba = to_rgba(dds)
            tp = tempfile.mktemp(suffix=".png"); png_write(tp, dds.w, dds.h, rgba)
            w, h, rgba2 = png_read(tp); os.remove(tp)
            new = from_rgba(dds, rgba2)
            if len(new) != len(dds.raw):
                bad += 1; print(f"  SIZE-DIFF {p}"); continue
            if dds.compressed():
                lossy += 1                       # size ok; DXT re-encode is lossy by design
            elif new == dds.raw:
                exact += 1
            else:
                bad += 1; print(f"  UNC NOT byte-identical {p}")
        except Exception as e:
            bad += 1; print(f"  ERR {p}: {e}")
    print(f"files={len(files)}  uncompressed byte-identical={exact}  DXT size-preserved={lossy}  bad={bad}")
    return 1 if bad else 0

if __name__ == "__main__":
    if len(sys.argv) < 2: print(__doc__); sys.exit(1)
    c = sys.argv[1]
    if   c == "export":      cmd_export(sys.argv[2], sys.argv[3])
    elif c == "apply":
        out = sys.argv[sys.argv.index("--out")+1] if "--out" in sys.argv else None
        cmd_apply(sys.argv[2], sys.argv[3], out)
    elif c == "export-tree": cmd_export_tree(sys.argv[2], sys.argv[3])
    elif c == "apply-tree":  cmd_apply_tree(sys.argv[2], sys.argv[3])
    elif c == "verify":      sys.exit(cmd_verify(sys.argv[2:]))
    else: print("unknown cmd", c); sys.exit(1)
