# -*- coding: utf-8 -*-
"""Flag non-Arabic, non-ASCII characters: the signature of a mangled write.

Pure ASCII and Arabic are both fine. Cyrillic (U+0400-U+04FF), CJK
(U+3000-U+9FFF), and stray CJK punctuation all mean a fragment of a
comment was replaced by noise. Reports ``path:line`` plus the offending
line with backslash escapes so it survives a cp1252 console.
"""

import io
import sys

BAD_RANGES = (
    (0x0080, 0x00A0),   # latin-1 supplement / C1 controls
    (0x0100, 0x024F),   # latin extended (accented) -- unexpected here
    (0x0370, 0x03FF),   # greek
    (0x0400, 0x04FF),   # cyrillic
    (0x0530, 0x058F),   # armenian
    (0x2000, 0x200F),   # invisible marks: bidi overrides hide text
    (0x2010, 0x2027),   # general punctuation (dashes/quotes allowed below)
    (0x2028, 0x202E),
    (0x3000, 0x303F),   # CJK punctuation
    (0x3040, 0x30FF),   # kana
    (0x4E00, 0x9FFF),   # unified ideographs
    (0xFF00, 0xFFEF),   # halfwidth/fullwidth forms
)

ALLOWED = {0x00AB, 0x00BB, 0x2014, 0x2013, 0x2026, 0x2019, 0x2018,
           0x201C, 0x201D, 0x2022, 0x00B7, 0x2192, 0x2190, 0x00D7,
           0x2264, 0x2265, 0x060C, 0x0640}

ARABIC = (0x0600, 0x06FF)


def bad_char(ch):
    code = ord(ch)
    if code in ALLOWED:
        return False
    if code < 0x0080:
        return False
    if ARABIC[0] <= code <= ARABIC[1]:
        return False
    for low, high in BAD_RANGES:
        if low <= code <= high:
            return True
    return False


dirty = 0
for path in sys.argv[1:]:
    text = io.open(path, encoding="utf-8-sig").read()
    for index, line in enumerate(text.splitlines(), 1):
        hits = [c for c in line if bad_char(c)]
        if not hits:
            continue
        dirty += 1
        codes = " ".join("U+%04X" % ord(c) for c in hits)
        print("%s:%d  %s\n    %s" % (path, index, codes,
                                    line.strip().encode("ascii", "backslashreplace").decode()))

print("SCAN", "dirty" if dirty else "clean")