#!/usr/bin/env python3
"""Submit every URL in a live sitemap to IndexNow (Bing, Yandex, Seznam, Naver share it).

The key must be served as https://<host>/<key>.txt on the same host — codeverse.nl,
dvrbridge.codeverse.nl and blog.codeverse.nl all use the same key, and each build
script writes the file into its deploy root. Run after every deploy that changes URLs:

    python3 tools/indexnow.py https://blog.codeverse.nl/sitemap.xml
    python3 tools/indexnow.py https://codeverse.nl/sitemap.xml

Google does not use IndexNow; submit the sitemap in Search Console for that.
"""
import json
import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

KEY = '733f7cbf4bbb2b3b8886cabbd6b23b0b'
ENDPOINT = 'https://api.indexnow.org/indexnow'
NS = {'sm': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
# Cloudflare's bot rules 403 the default urllib agent, so identify ourselves.
UA = {'User-Agent': 'codeverse-indexnow/1.0 (+https://codeverse.nl)'}


def get(url):
    return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=20)


def main(sitemap_url):
    host = urllib.parse.urlparse(sitemap_url).hostname
    with get(sitemap_url) as r:
        urls = [e.text.strip() for e in ET.fromstring(r.read()).findall('.//sm:loc', NS)]
    if not urls:
        raise SystemExit('sitemap has no <loc> entries')

    key_url = f'https://{host}/{KEY}.txt'
    with get(key_url) as r:
        if r.read().decode().strip() != KEY:
            raise SystemExit(f'{key_url} does not contain the key — deploy first')

    body = json.dumps({'host': host, 'key': KEY, 'keyLocation': key_url, 'urlList': urls}).encode()
    req = urllib.request.Request(ENDPOINT, data=body, headers={'Content-Type': 'application/json; charset=utf-8', **UA})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            status = r.status
    except urllib.error.HTTPError as e:
        status = e.code
    meaning = {200: 'OK', 202: 'accepted (key validation pending)', 400: 'bad request',
               403: 'forbidden — key file not found or mismatched', 422: 'URLs do not belong to host / key invalid',
               429: 'too many requests'}.get(status, 'unexpected')
    print(f'IndexNow {status} {meaning}: {len(urls)} URL(s) from {host}')
    for u in urls:
        print('  ', u)
    return 0 if status in (200, 202) else 1


if __name__ == '__main__':
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    sys.exit(main(sys.argv[1]))
