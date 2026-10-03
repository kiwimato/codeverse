#!/usr/bin/env python3
"""Re-derive the CSP script-src hash allow-list in site/_headers.

Every page carries an inline <script type="application/ld+json"> block. The CSP
allow-lists each one by SHA-256 rather than falling back to 'unsafe-inline', so
the hashes have to be refreshed whenever any page's JSON-LD changes — otherwise
the browser silently drops the structured data and the rich results go with it.

Run after editing any page, and always after build-service-pages.py:

    python3 tools/refresh-csp.py
"""
import base64
import glob
import hashlib
import io
import json
import os
import re

SITE = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'site')
BLOCK = re.compile(r'<script type="application/ld\+json">(.*?)</script>', re.S)


def main():
    hashes = set()
    for path in sorted(glob.glob(os.path.join(SITE, '*.html')) +
                       glob.glob(os.path.join(SITE, '*', 'index.html'))):
        src = io.open(path, encoding='utf-8').read()
        for m in BLOCK.finditer(src):
            json.loads(m.group(1))  # fail loudly rather than shipping broken JSON-LD
            hashes.add('sha256-' + base64.b64encode(
                hashlib.sha256(m.group(1).encode('utf-8')).digest()).decode())

    headers = os.path.join(SITE, '_headers')
    hs = io.open(headers, encoding='utf-8').read()
    joined = ' '.join(f"'{h}'" for h in sorted(hashes))
    new, n = re.subn(r"script-src 'self'[^;]*;", f"script-src 'self' {joined};", hs, count=1)
    if not n:
        raise SystemExit('no script-src directive found in site/_headers')
    io.open(headers, 'w', encoding='utf-8').write(new)
    print(f'{len(hashes)} inline JSON-LD block(s) allow-listed')


if __name__ == '__main__':
    main()
