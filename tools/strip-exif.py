#!/usr/bin/env python3
"""Copy JPEGs into a post directory with all metadata removed.

Phone photos carry EXIF: camera model, timestamps, often GPS coordinates of the
living room the photo was taken in. Nothing on the blog should ship that. This
drops every APPn and COM segment (EXIF, XMP, ICC, thumbnails) and keeps only the
image data, so the file still decodes identically. Pure stdlib — no Pillow.

    python3 tools/strip-exif.py ~/Downloads/PXL_1234.jpg posts/<slug>/hero.jpg
    python3 tools/strip-exif.py ~/Downloads/*.jpg posts/<slug>/      # keeps the names

Caveat: a photo whose EXIF says "rotate me 90°" loses that hint, so check the
result is the right way up. Pixel phones write already-rotated pixels, so this
has not bitten yet.
"""
import io
import os
import struct
import sys


def strip(src, dst):
    d = io.open(src, 'rb').read()
    if d[:2] != b'\xff\xd8':
        raise SystemExit(f'{src}: not a JPEG')
    out, i = [d[:2]], 2
    while i < len(d):
        if d[i] != 0xFF:
            raise SystemExit(f'{src}: corrupt marker at byte {i}')
        m = d[i + 1]
        if m in (0xD9, 0xDA):          # EOI, or start of scan: the rest is image data
            out.append(d[i:])
            break
        L = struct.unpack('>H', d[i + 2:i + 4])[0]
        seg = d[i:i + 2 + L]
        metadata = (0xE0 <= m <= 0xEF and m != 0xEE) or m == 0xFE   # APPn except Adobe APP14; COM
        if not metadata:
            out.append(seg)
        i += 2 + L
    data = b''.join(out)
    io.open(dst, 'wb').write(data)
    print(f'{os.path.basename(dst)}: {len(d) // 1024}K -> {len(data) // 1024}K')


def main(argv):
    if len(argv) < 2:
        raise SystemExit(__doc__)
    *srcs, dst = argv
    if os.path.isdir(dst) or dst.endswith('/') or len(srcs) > 1:
        os.makedirs(dst, exist_ok=True)
        for s in srcs:
            strip(s, os.path.join(dst, os.path.basename(s).lower()))
    else:
        strip(srcs[0], dst)


if __name__ == '__main__':
    main(sys.argv[1:])
