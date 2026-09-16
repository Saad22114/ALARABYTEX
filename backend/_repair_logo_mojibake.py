# -*- coding: utf-8 -*-
"""Lossless repair: frontend/app/settings/page.tsx was corrupted when PowerShell
Get-Content (ANSI/cp1252) read the UTF-8 file and Set-Content re-wrote it,
turning every Arabic (UTF-8) byte into cp1252 mojibake.

Reverse: C = UTF8(cp1252_decode(B_original))
   => B_original = cp1252_encode( UTF8_decode(C) )

The 5 cp1252-undefined control bytes (0x81 0x8D 0x8F 0x90 0x9D) appear in real
Arabic UTF-8 continuations, so cp1252.encode would throw on them. We use a
manual byte table that passes those through as their identity byte.

Author: fix routine. Idempotent-safe: refuses to run if file already has real
Arabic.
"""
import io, sys

PATH = r"D:\QOMASH\site 3 open code\frontend\app\settings\page.tsx"
HAS_BOM = True

# cp1252 char->byte for the 0x80..0x9F block (with undefined -> itself)
CP1252_80 = {
    0x20AC: 0x80, 0x0081: 0x81, 0x201A: 0x82, 0x0192: 0x83, 0x201E: 0x84,
    0x2026: 0x85, 0x2020: 0x86, 0x2021: 0x87, 0x02C6: 0x88, 0x2030: 0x89,
    0x0160: 0x8A, 0x2039: 0x8B, 0x0152: 0x8C, 0x008D: 0x8D, 0x017D: 0x8E,
    0x008F: 0x8F, 0x0090: 0x90, 0x2018: 0x91, 0x2019: 0x92, 0x201C: 0x93,
    0x201D: 0x94, 0x2022: 0x95, 0x2013: 0x96, 0x2014: 0x97, 0x02DC: 0x98,
    0x2122: 0x99, 0x0161: 0x9A, 0x203A: 0x9B, 0x0153: 0x9C, 0x009D: 0x9D,
    0x017E: 0x9E, 0x0178: 0x9F,
}

def encode_cp1252(s):
    out = bytearray()
    for ch in s:
        o = ord(ch)
        if o < 0x80:                          # ASCII + CR/LF/TAB/controls: identical bytes
            out.append(o)
        elif 0xA0 <= o <= 0xFF:          # latin-1 identity
            out.append(o)
        elif o in CP1252_80:
            out.append(CP1252_80[o])
        elif 0x0080 <= o <= 0x009F:      # other undefined control pass-through
            out.append(o)
        else:
            raise ValueError("unmappable cp1252 char U+%04X" % o)
    return bytes(out)

def main():
    raw = open(PATH, "rb").read()
    has_bom = raw[:3] == b"\xef\xbb\xbf"
    body = raw[3:] if has_bom else raw

    moj = body.decode("utf-8")           # UTF-8 shell -> mojibake string

    # refuse if already repaired (has real Arabic)
    if any(0x0600 <= ord(c) <= 0x06FF for c in moj):
        print("ALREADY CLEAN / HAS REAL ARABIC - aborting (no-op)")
        return

    old_bytes = encode_cp1252(moj)       # back to original UTF-8 bytes
    fixed = old_bytes.decode("utf-8")    # clean Arabic

    # sanity = the fixed text must contain real Arabic and no mojibake
    arab = sum(1 for c in fixed if 0x0600 <= ord(c) <= 0x06FF)
    mozi = sum(1 for c in fixed if
               0x00C0 <= ord(c) <= 0x00FF or ord(c) in CP1252_80)
    if arab == 0:
        raise SystemExit("repair produced ZERO arabic - something wrong, aborting")
    print("recovered real-Arabic chars: %d, remaining mojibake chars: %d" % (arab, mozi))

    # code must be byte-identical ASCII-wise: compare ascii-only projection
    import re
    la = re.sub(rb"[^\x20-\x7e]", b"", old_bytes)
    lb = re.sub(rb"[^\x20-\x7e]", b"", raw)
    print("ascii bytes identical to original:", la == lb)

    data = (b"\xef\xbb\xbf" + fixed.encode("utf-8")) if has_bom else fixed.encode("utf-8")
    with open(PATH, "wb") as fh:
        fh.write(data)
    print("WROTE repaired file (BOM preserved: %s), size %d -> %d bytes"
          % (has_bom, len(raw), len(data)))
    print("OK")

if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    main()
