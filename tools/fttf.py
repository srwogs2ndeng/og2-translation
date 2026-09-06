#!/usr/bin/env python3
"""
fttf.py - decoder/encoder for the PS3 "FTTF" font container used by
Super Robot Wars OG2 (font.bin, exFont0*.bin).

FORMAT (big-endian header, reverse-engineered from the files + EBOOT parser
FTTF_init @ VA 0x5cce98 in the decrypted EBOOT):

  0x00  u32  magic 'FTTF' (0x46545446)
  0x04  u32  total file size
  0x08  u32  glyph cell width  (32)
  0x0c  u32  glyph cell height (32)
  0x10  u32  flags/format code (0x01000300)
  0x14  u32  offset to the TEXTURE DESCRIPTOR ("TexDesc")
  0x50 ..    master page table : 32 records * 0x20 bytes.  Each record holds
             up to 8 u32 pointers (at +4,+8,...,+0x20); nonzero ones point to
             0x400-byte code->glyph sub-tables.  (Pointers are file-relative
             offsets, relocated to absolute at load time.)
  <sub>      each sub-table = 256 entries * 4 bytes, indexed by a code byte.
             entry = 00 B1 B2 B3  (big-endian u32, top byte 0)
               B2 = atlas cell COLUMN (0..31)
               B3 = atlas cell ROW
               B1 = secondary field (NOT the runtime advance width - the game
                    sets advance at runtime/via EBOOT, editing B1 in the file
                    does not move the pen; see report).
  TexDesc:   (at header[0x14])
      +0x00 u32  0x020101ff   format/flags
      +0x04 u32  atlas data size in bytes  (== W*H, since BC3 averages 1 B/px)
      +0x20 u16  atlas texture WIDTH  (px)   -- font.bin: 1024
      +0x22 u16  atlas texture HEIGHT (px)   -- font.bin: 4096 (declared; file
                 may be truncated of trailing empty rows)
  ATLAS:     DXT5 / BC3 compressed, 16 bytes per 4x4 block, row-of-blocks major,
             pitch = (W/4) blocks.  Both the alpha channel AND the RGB (as
             white luminance) carry the glyph coverage.  A 32x32 glyph cell =
             8x8 blocks = 1024 bytes, but blocks are NOT contiguous per glyph -
             they are addressed by pixel (col*32, row*32) in the raster.

Because BC3 blocks are fixed size, redrawing a glyph is OFFSET-PRESERVING:
re-encoding a 32x32 cell always produces the same 1024 bytes of block data in
the same positions -> safe for the game's size-sensitive loader.
"""
import struct, sys, os, argparse

MAGIC = 0x46545446

# atlas offsets that are not simply (filesize - atlas_size); verified by render.
KNOWN_ATLAS_OFF = {0x418200: 0x20000}   # keyed by file size (font.bin)

class FTTF:
    def __init__(self, data):
        assert struct.unpack('>I', data[:4])[0] == MAGIC, "not an FTTF file"
        self.d = bytearray(data)
        self.size   = struct.unpack('>I', data[4:8])[0]
        self.cell_w = struct.unpack('>I', data[8:12])[0]
        self.cell_h = struct.unpack('>I', data[12:16])[0]
        self.td     = struct.unpack('>I', data[0x14:0x18])[0]
        td = self.td
        self.atlas_size = struct.unpack('>I', data[td+4:td+8])[0]
        self.W = struct.unpack('>H', data[td+0x20:td+0x22])[0]
        self.H = struct.unpack('>H', data[td+0x22:td+0x24])[0]
        self.BPR = self.W // 4                      # blocks per row
        self.cols = self.W // self.cell_w           # glyph columns (32)
        self.atlas_off = self._find_atlas()
        # rows actually stored in the file
        self.stored_h = ((len(self.d) - self.atlas_off) // self.BPR // 16) * 4
        self.rows = self.stored_h // self.cell_h

    def _find_atlas(self):
        cand = len(self.d) - self.atlas_size
        off = KNOWN_ATLAS_OFF.get(len(self.d))
        if off is not None:
            return off
        if cand > 0:
            return cand & ~0x7f
        return (self.td + 0x80) & ~0x7f

    # ---- DXT5 alpha decode (coverage) ----
    def _block_alpha(self, off):
        a0, a1 = self.d[off], self.d[off+1]
        bits = int.from_bytes(self.d[off+2:off+8], 'little')
        a = [a0, a1]
        if a0 > a1:
            for i in range(1, 7): a.append(((7-i)*a0 + i*a1)//7)
        else:
            for i in range(1, 5): a.append(((5-i)*a0 + i*a1)//5)
            a += [0, 255]
        return [a[(bits >> (3*i)) & 7] for i in range(16)]

    def pixel(self, x, y):
        bx, by = x//4, y//4
        off = self.atlas_off + (by*self.BPR + bx)*16
        return self._block_alpha(off)[(y % 4)*4 + (x % 4)]

    def cell_image(self, col, row):
        from PIL import Image
        im = Image.new('L', (self.cell_w, self.cell_h)); px = im.load()
        # decode block-wise for speed
        for byb in range(self.cell_h//4):
            for bxb in range(self.cell_w//4):
                bx = col*(self.cell_w//4) + bxb
                by = row*(self.cell_h//4) + byb
                off = self.atlas_off + (by*self.BPR + bx)*16
                blk = self._block_alpha(off)
                for i in range(16):
                    px[bxb*4 + (i % 4), byb*4 + (i//4)] = blk[i]
        return im

    def decode_full(self):
        """Return a PIL 'L' image of the whole stored atlas (alpha=coverage)."""
        from PIL import Image
        H = self.stored_h
        im = Image.new('L', (self.W, H)); px = im.load()
        for by in range(H//4):
            for bx in range(self.BPR):
                off = self.atlas_off + (by*self.BPR + bx)*16
                if off+8 > len(self.d): continue
                blk = self._block_alpha(off)
                for i in range(16):
                    px[bx*4 + (i % 4), by*4 + (i//4)] = blk[i]
        return im

    # ---- glyph table ----
    def entries(self):
        """Yield (sub_off, code, col, row, b1) for every nonzero sub-table entry."""
        # sub-tables span from just after the master table to the TexDesc.
        o = 0x580
        while o < self.td:
            b = self.d[o:o+4]
            if b and b[0] == 0 and (b[1] | b[2] | b[3]):
                yield o, (o & 0x3ff)//4, b[2], b[3], b[1]
            o += 4

    def cell_to_entry(self):
        m = {}
        for off, code, col, row, b1 in self.entries():
            m.setdefault((col, row), off)
        return m

    # ---- DXT5 encode (from an 'L' coverage image) ----
    @staticmethod
    def _encode_block_alpha(vals):
        a0, a1 = max(vals), min(vals)
        if a0 == a1:
            a0 = min(255, a1+1)
        pal = [a0, a1] + [((7-i)*a0 + i*a1)//7 for i in range(1, 7)]
        bits = 0
        for i, v in enumerate(vals):
            best = min(range(8), key=lambda k: abs(pal[k]-v))
            bits |= best << (3*i)
        return bytes([a0, a1]) + bits.to_bytes(6, 'little')

    @staticmethod
    def _encode_block_color(vals):
        # store white(where ink)/black via 565 endpoints white/black, 2-bit idx
        c_white, c_black = 0xffff, 0x0000
        out = struct.pack('<HH', c_white, c_black)
        idx = 0
        for i, v in enumerate(vals):
            # 0 = white endpoint, 1 = black endpoint (c0>c1 => 4-colour, pick nearest of the two ends)
            k = 0 if v >= 128 else 1
            idx |= k << (2*i)
        return out + idx.to_bytes(4, 'little')

    def write_cell(self, col, row, img):
        """Re-encode a 32x32 'L' coverage image into the atlas cell in-place."""
        px = img.convert('L').load()
        for byb in range(self.cell_h//4):
            for bxb in range(self.cell_w//4):
                vals = [px[bxb*4 + (i % 4), byb*4 + (i//4)] for i in range(16)]
                bx = col*(self.cell_w//4) + bxb
                by = row*(self.cell_h//4) + byb
                off = self.atlas_off + (by*self.BPR + bx)*16
                self.d[off:off+8]    = self._encode_block_alpha(vals)
                self.d[off+8:off+16] = self._encode_block_color(vals)

    def save(self, path):
        open(path, 'wb').write(self.d)


def cmd_decode(a):
    f = FTTF(open(a.file, 'rb').read())
    print(f"cell {f.cell_w}x{f.cell_h}  atlas {f.W}x{f.H} (stored {f.stored_h})"
          f"  atlas_off=0x{f.atlas_off:x}  grid {f.cols}x{f.rows}")
    im = f.decode_full()
    im.save(a.out)
    print("wrote", a.out)


def cmd_dump(a):
    f = FTTF(open(a.file, 'rb').read())
    for off, code, col, row, b1 in f.entries():
        print(f"0x{off:06x} code=0x{code:02x} cell=({col:2d},{row:3d}) b1=0x{b1:02x}")


def cmd_cell(a):
    f = FTTF(open(a.file, 'rb').read())
    f.cell_image(a.col, a.row).resize((256, 256)).save(a.out)
    print("wrote", a.out)


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description="FTTF font decoder/encoder")
    sub = ap.add_subparsers(dest='cmd', required=True)
    p = sub.add_parser('decode', help='dump full atlas coverage to PNG'); p.add_argument('file'); p.add_argument('out'); p.set_defaults(fn=cmd_decode)
    p = sub.add_parser('dump',   help='list glyph-table entries');        p.add_argument('file'); p.set_defaults(fn=cmd_dump)
    p = sub.add_parser('cell',   help='render one glyph cell');           p.add_argument('file'); p.add_argument('col', type=int); p.add_argument('row', type=int); p.add_argument('out'); p.set_defaults(fn=cmd_cell)
    args = ap.parse_args()
    args.fn(args)
