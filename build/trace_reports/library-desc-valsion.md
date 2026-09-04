# og2 trace report - library-desc-valsion

source: `../rpcs3-instrumented/og2_trace.log`

## Watched ranges

- `session-start`

## Reads (1 unique PCs)

| guest PC | hits | first EA | val | LR | call stack | known? |
|---|---|---|---|---|---|---|
| `0x0994AF8` | 1 | `0x300E6D73` | 0x74 | `0x082D538` | `0x82d538>0x82e418>0x27bb64>0x27d5f8>0x27dc84` |  |

## Next step

Disassemble around the top unannotated PCs:
`python tools/eboot_analyze.py` (or capstone at foff = cia - 0x10000 in the
decrypted EBOOT.elf) and look for the advance/condense math near each PC.
