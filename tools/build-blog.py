#!/usr/bin/env python3
"""Build blog.codeverse.nl from the Markdown posts in posts/.

Zero dependencies, on purpose — the main site has no build step and no external
requests, and the blog follows suit. A small Markdown converter lives at the
bottom of this file; it covers what a repair write-up or a technical note needs
(headings, lists, fenced code, tables, images with captions, quotes, links) and
nothing more.

Source layout (posts/ is never deployed):

    posts/<slug>/en.md        English version   -> https://blog.codeverse.nl/<slug>/
    posts/<slug>/nl.md        Dutch version     -> https://blog.codeverse.nl/nl/<slug>/
    posts/<slug>/*.jpg|png    images, shared by both languages, copied to blog/<slug>/

A post may exist in one language only. When both exist, the two pages link to
each other and carry hreflang alternates; when one is missing, the switcher on
the other page says so instead of linking to a 404.

Front matter is plain `key: value` lines between two `---` lines:

    ---
    title: How I fixed the steering rod on a Lovens Explorer
    description: One or two sentences. Used for the index, meta tags and the feed.
    date: 2026-09-20
    updated: 2026-09-25        # optional
    tags: repair, bakfiets     # optional, comma-separated; see TAGS below
    image: hero.jpg            # optional, relative to the post dir; social card
    draft: true                # optional; skipped unless --drafts is given
    ---

Output (everything under blog/, which IS the deploy root):

    python3 tools/build-blog.py                     # -> blog/
    python3 tools/build-blog.py --drafts --out /tmp/x   # preview drafts elsewhere

Deploy:

    wrangler pages deploy ~/code/codeverse/blog --project-name=codeverse-blog --branch=main
"""
import argparse
import base64
import datetime as dt
import glob
import hashlib
import html
import io
import json
import os
import re
import shutil
import zoneinfo

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
POSTS = os.path.join(ROOT, 'posts')
SITE = os.path.join(ROOT, 'site')          # the main site — CSS/JS/favicon are reused from here
OUT_DEFAULT = os.path.join(ROOT, 'blog')

HOST = 'blog.codeverse.nl'                 # <- the one place the hostname lives
ORIGIN = f'https://{HOST}'
MAIN = 'https://codeverse.nl'
AUTHOR = 'Mihai Cindea'
INDEXNOW_KEY = '733f7cbf4bbb2b3b8886cabbd6b23b0b'   # same key as codeverse.nl and dvrbridge; served at /<key>.txt
TZ = zoneinfo.ZoneInfo('Europe/Amsterdam')

LANGS = ['en', 'nl']                       # first one is the default (x-default, root URL)

# Tag slug -> display name per language. A tag not listed here is shown as-is.
# 'repair' is the "Repair corner" — bakfiets, tools, things around the house.
TAGS = {
    'repair':     {'en': 'Repair corner',   'nl': 'Reparatiehoek'},
    'opensource': {'en': 'Open source',     'nl': 'Open source'},
    'bakfiets':   {'en': 'Bakfiets',        'nl': 'Bakfiets'},
    'cloud':      {'en': 'Cloud & DevOps',  'nl': 'Cloud & DevOps'},
    'homelab':    {'en': 'Homelab',         'nl': 'Homelab'},
    'notes':      {'en': 'Notes',           'nl': 'Notities'},
}

# Optional blurb for a tag page: becomes both its lede and its meta description.
# A tag with no entry falls back to the generic "Posts filed under X" line.
TAG_INTRO = {
    'opensource': {
        'en': 'Small open source tools, each written to fix one specific problem, like '
              'hardware that would not behave or a machine that needed persuading. All on GitHub.',
        'nl': 'Kleine opensourcetools, elk geschreven voor één specifiek probleem, zoals '
              'hardware die niet wilde meewerken of een machine die wat overtuiging nodig had. Alles staat op GitHub.',
    },
}

# Tags promoted to the site navigation, in order. Each needs a 'nav_<slug>' label in
# UI below; a tag with nothing published in a language is dropped from that language's nav.
NAV_TAGS = ['repair', 'opensource']

UI = {
    'en': dict(
        site_name='Codeverse blog',
        tagline='Repairs, infrastructure and other things worth writing down.',
        index_title='Codeverse blog — repairs, infrastructure and notes',
        index_desc='Notes by Mihai Cindea: bakfiets and household repairs, cloud and DevOps '
                   'engineering, and whatever else was worth writing down. In English and Dutch.',
        nav_blog='All posts', nav_repair='Repair corner', nav_opensource='Open source',
        nav_main='codeverse.nl',
        nav_hire='Work with me', switch_label='Nederlands', switch_missing='Not available in Dutch',
        by='By', published='Published', updated='Updated', read='min read',
        tagged='Filed under', posts_tagged='Posts filed under', all_posts='All posts',
        empty='Nothing published yet. The first post is on its way.',
        latest='Latest posts', tags_h='Browse by topic', feed='RSS feed',
        back='Back to all posts', about_h='About the author',
        about=('Mihai Cindea is a freelance cloud and DevOps engineer in Utrecht. The day job is '
               'AWS, Terraform and CI/CD. The blog covers that, and anything else that got '
               'taken apart and put back together.'),
        crumb_home='Blog', not_found='Page not found',
        not_found_lede='That page does not exist here. It may have moved, or the address was mistyped.',
        skip='Skip to content', menu_open='Open menu', crumbs='Breadcrumb', footer_tag='Notes from Utrecht, NL',
        lang_name='English', locale='en_GB', html_lang='en',
    ),
    'nl': dict(
        site_name='Codeverse blog',
        tagline='Reparaties, infrastructuur en andere dingen die het opschrijven waard zijn.',
        index_title='Codeverse blog — reparaties, infrastructuur en notities',
        index_desc='Notities van Mihai Cindea: bakfiets- en huishoudelijke reparaties, cloud- en '
                   'DevOps-engineering, en wat verder het opschrijven waard was. In het Nederlands en Engels.',
        nav_blog='Alle berichten', nav_repair='Reparatiehoek', nav_opensource='Open source',
        nav_main='codeverse.nl',
        nav_hire='Samenwerken', switch_label='English', switch_missing='Niet beschikbaar in het Engels',
        by='Door', published='Gepubliceerd', updated='Bijgewerkt', read='min lezen',
        tagged='Onderwerp', posts_tagged='Berichten over', all_posts='Alle berichten',
        empty='Nog niets gepubliceerd. Het eerste bericht komt eraan.',
        latest='Laatste berichten', tags_h='Op onderwerp', feed='RSS-feed',
        back='Terug naar alle berichten', about_h='Over de auteur',
        about=('Mihai Cindea is freelance cloud- en DevOps-engineer in Utrecht. Overdag is dat '
               'AWS, Terraform en CI/CD. Dit blog gaat daarover, en over alles wat verder uit '
               'elkaar is gehaald en weer in elkaar gezet.'),
        crumb_home='Blog', not_found='Pagina niet gevonden',
        not_found_lede='Deze pagina bestaat hier niet. Misschien is ze verplaatst, of is het adres verkeerd getypt.',
        skip='Naar de inhoud', menu_open='Menu openen', crumbs='Kruimelpad', footer_tag='Notities uit Utrecht, NL',
        lang_name='Nederlands', locale='nl_NL', html_lang='nl',
    ),
}

MONTHS = {
    'en': ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August',
           'September', 'October', 'November', 'December'],
    'nl': ['januari', 'februari', 'maart', 'april', 'mei', 'juni', 'juli', 'augustus',
           'september', 'oktober', 'november', 'december'],
}

E = html.escape


# ----------------------------------------------------------------------------
# URLs
# ----------------------------------------------------------------------------

def prefix(lang):
    return '' if lang == LANGS[0] else f'/{lang}'


def index_path(lang):
    return prefix(lang) + '/'


def post_path(lang, slug):
    return f'{prefix(lang)}/{slug}/'


def tag_path(lang, tag):
    return f'{prefix(lang)}/tag/{tag}/'


def feed_path(lang):
    return f'{prefix(lang)}/feed.xml'


def tag_name(tag, lang):
    return TAGS.get(tag, {}).get(lang, tag)


def fmt_date(d, lang):
    return f'{d.day} {MONTHS[lang][d.month - 1]} {d.year}'


# ----------------------------------------------------------------------------
# Posts
# ----------------------------------------------------------------------------

class Post:
    def __init__(self, slug, lang, meta, body_md):
        self.slug, self.lang, self.meta = slug, lang, meta
        for k in ('title', 'description', 'date'):
            if k not in meta:
                raise SystemExit(f'posts/{slug}/{lang}.md: missing "{k}" in front matter')
        self.title = meta['title']
        self.description = meta['description']
        self.date = dt.date.fromisoformat(meta['date'])
        self.updated = dt.date.fromisoformat(meta['updated']) if meta.get('updated') else None
        self.tags = [t.strip() for t in meta.get('tags', '').split(',') if t.strip()]
        self.image = meta.get('image') or None
        self.draft = str(meta.get('draft', '')).lower() in ('true', 'yes', '1')
        self.body_md = body_md
        self.html = md_to_html(body_md, f'/{slug}/')
        words = len(re.findall(r'\w+', re.sub(r'```.*?```', '', body_md, flags=re.S)))
        self.minutes = max(1, round(words / 200))
        self.sibling = None  # the same post in the other language, filled in later

    @property
    def path(self):
        return post_path(self.lang, self.slug)

    @property
    def url(self):
        return ORIGIN + self.path

    @property
    def image_url(self):
        if not self.image:
            return f'{ORIGIN}/assets/img/og.png'
        if re.match(r'^https?://', self.image):
            return self.image
        return f'{ORIGIN}/{self.slug}/{self.image.lstrip("./")}'


def parse_front_matter(src, where):
    m = re.match(r'^---\s*\n(.*?)\n---\s*\n?(.*)$', src, re.S)
    if not m:
        raise SystemExit(f'{where}: no front matter block')
    meta = {}
    for line in m.group(1).splitlines():
        line = line.split(' #')[0].rstrip() if not line.lstrip().startswith('#') else ''
        if not line.strip():
            continue
        k, _, v = line.partition(':')
        meta[k.strip()] = v.strip().strip('"').strip("'")
    return meta, m.group(2)


def load_posts(include_drafts):
    posts = []
    for d in sorted(glob.glob(os.path.join(POSTS, '*'))):
        if not os.path.isdir(d):
            continue
        slug = os.path.basename(d)
        if not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', slug):
            raise SystemExit(f'posts/{slug}: directory name must be a lowercase-and-dashes slug')
        by_lang = {}
        for lang in LANGS:
            f = os.path.join(d, f'{lang}.md')
            if not os.path.exists(f):
                continue
            meta, body = parse_front_matter(io.open(f, encoding='utf-8').read(), f'posts/{slug}/{lang}.md')
            p = Post(slug, lang, meta, body)
            if p.draft and not include_drafts:
                continue
            by_lang[lang] = p
        if len(by_lang) == 2:
            a, b = by_lang[LANGS[0]], by_lang[LANGS[1]]
            a.sibling, b.sibling = b, a
        posts.extend(by_lang.values())
    posts.sort(key=lambda p: (p.date, p.slug), reverse=True)
    return posts


# ----------------------------------------------------------------------------
# Page chrome
# ----------------------------------------------------------------------------

def head(lang, title, desc, path, *, alternates, og_type='website', image=None,
         robots='index, follow, max-image-preview:large, max-snippet:-1', extra=''):
    """`alternates` maps lang -> path for every language this page exists in."""
    ui = UI[lang]
    url = ORIGIN + path
    alt = '\n'.join(f'<link rel="alternate" hreflang="{l}" href="{ORIGIN}{p}">'
                    for l, p in sorted(alternates.items()))
    if LANGS[0] in alternates:
        alt += f'\n<link rel="alternate" hreflang="x-default" href="{ORIGIN}{alternates[LANGS[0]]}">'
    other_locales = '\n'.join(f'<meta property="og:locale:alternate" content="{UI[l]["locale"]}">'
                              for l in alternates if l != lang)
    return f'''<!DOCTYPE html>
<html lang="{ui['html_lang']}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{E(title)}</title>
<meta name="description" content="{E(desc)}">
<link rel="canonical" href="{url}">
{alt}
<meta name="robots" content="{robots}">
<meta name="author" content="{AUTHOR}">

<meta property="og:type" content="{og_type}">
<meta property="og:site_name" content="{E(ui['site_name'])}">
<meta property="og:title" content="{E(title)}">
<meta property="og:description" content="{E(desc)}">
<meta property="og:url" content="{url}">
<meta property="og:locale" content="{ui['locale']}">
{other_locales}
<meta property="og:image" content="{image or ORIGIN + '/assets/img/og.png'}">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{E(title)}">
<meta name="twitter:description" content="{E(desc)}">
<meta name="twitter:image" content="{image or ORIGIN + '/assets/img/og.png'}">
{extra}
<link rel="alternate" type="application/rss+xml" title="{E(ui['site_name'])} ({ui['lang_name']})" href="{ORIGIN}{feed_path(lang)}">
<link rel="icon" href="/favicon.svg" type="image/svg+xml">
<link rel="alternate icon" href="/favicon.ico">
<link rel="stylesheet" href="/assets/css/style.css">
<link rel="stylesheet" href="/assets/css/blog.css">
</head>
<body>

<a class="skip-link" href="#main">{E(ui['skip'])}</a>
'''


def header(lang, switch):
    """`switch` is (label, href) for the language switcher, or (label, None) when
    the page has no counterpart in the other language."""
    ui = UI[lang]
    label, href = switch
    if href:
        sw = f'<a class="lang-switch" href="{href}" hreflang="{"nl" if lang == "en" else "en"}" lang="{"nl" if lang == "en" else "en"}">{E(label)}</a>'
    else:
        sw = f'<span class="lang-switch is-disabled" title="{E(label)}">{"NL" if lang == "en" else "EN"}</span>'
    nav_tags = ''.join(
        f'      <a href="{tag_path(lang, t)}">{E(ui[f"nav_{t}"])}</a>\n'
        for t in NAV_TAGS if t in HAS_TAG[lang])
    return f'''
<header class="site-header">
  <div class="wrap header-inner">
    <a class="brand" href="{index_path(lang)}" aria-label="{E(ui['site_name'])}">
      <svg class="brand-mark" width="28" height="28" viewBox="0 0 32 32" aria-hidden="true" focusable="false">
        <path d="M16 2.6 28 9.3v13.4L16 29.4 4 22.7V9.3z" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round"/>
        <path d="M20.6 12.2a5.8 5.8 0 1 0 0 7.6" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round"/>
      </svg>
      <span class="brand-text">Codeverse <span class="brand-sub">blog</span></span>
    </a>

    <button class="nav-toggle" id="nav-toggle" aria-expanded="false" aria-controls="site-nav" aria-label="{E(ui['menu_open'])}">
      <span></span><span></span><span></span>
    </button>

    <nav class="site-nav" id="site-nav" aria-label="Primary">
      <a href="{index_path(lang)}">{E(ui['nav_blog'])}</a>
{nav_tags}      <a href="{MAIN}/">{E(ui['nav_main'])}</a>
      {sw}
      <a class="nav-cta" href="{MAIN}/#contact">{E(ui['nav_hire'])}</a>
    </nav>
  </div>
</header>

<main id="main">
'''


def footer(lang, ld):
    ui = UI[lang]
    return f'''
</main>

<footer class="site-footer">
  <div class="wrap footer-inner">
    <p class="footer-brand">
      <span class="brand-text">Codeverse</span>
      <span class="footer-tag">{E(ui['footer_tag'])}</span>
    </p>
    <p class="footer-links">
      <a href="{feed_path(lang)}">{E(ui['feed'])}</a>
      · <a href="{MAIN}/">codeverse.nl</a>
      · <a href="https://github.com/kiwimato" rel="me noopener">GitHub</a>
    </p>
    <p class="footer-copy">&copy; <span id="year">{dt.date.today().year}</span> Codeverse — {AUTHOR}. All rights reserved.</p>
  </div>
</footer>

<script type="application/ld+json">
{json.dumps(ld, ensure_ascii=False, indent=2)}
</script>

<script src="/assets/js/main.js" defer></script>
</body>
</html>
'''


def tag_chips(post, lang):
    if not post.tags:
        return ''
    chips = ' '.join(f'<a class="tag" href="{tag_path(lang, t)}">{E(tag_name(t, lang))}</a>' for t in post.tags)
    return f'<span class="tags">{chips}</span>'


def post_card(p, lang):
    ui = UI[lang]
    return f'''      <li class="post-card">
        <time datetime="{p.date.isoformat()}">{fmt_date(p.date, lang)}</time>
        <div>
          <h2><a href="{p.path}">{E(p.title)}</a></h2>
          <p>{E(p.description)}</p>
          <p class="post-card-meta">{tag_chips(p, lang)}<span class="read-time">{p.minutes} {ui['read']}</span></p>
        </div>
      </li>'''


# ----------------------------------------------------------------------------
# Pages
# ----------------------------------------------------------------------------

def render_list(lang, posts, all_tags, *, tag=None):
    """The front page (tag=None) or a tag page."""
    ui = UI[lang]
    if tag:
        title = f'{ui["posts_tagged"]} {tag_name(tag, lang)} — {ui["site_name"]}'
        intro = TAG_INTRO.get(tag, {}).get(lang)
        desc = intro or f'{ui["posts_tagged"]} {tag_name(tag, lang)}. {ui["index_desc"]}'
        path = tag_path(lang, tag)
        h1 = tag_name(tag, lang)
        alternates = {l: tag_path(l, tag) for l in LANGS if any(tag in q.tags for q in all_tags[l])}
    else:
        title, desc, path, h1 = ui['index_title'], ui['index_desc'], index_path(lang), ui['site_name']
        alternates = {l: index_path(l) for l in LANGS}

    other = [l for l in LANGS if l != lang][0]
    switch = (ui['switch_label'], alternates.get(other))

    cards = '\n'.join(post_card(p, lang) for p in posts) if posts else \
        f'      <li class="post-empty">{E(ui["empty"])}</li>'

    tags_here = sorted({t for p in all_tags[lang] for t in p.tags}, key=lambda t: tag_name(t, lang))
    tag_links = '\n'.join(
        f'        <li><a class="tag{" is-active" if t == tag else ""}" href="{tag_path(lang, t)}">{E(tag_name(t, lang))}</a></li>'
        for t in tags_here)

    crumbs = ''
    if tag:
        crumbs = f'''      <nav class="crumbs" aria-label="{E(ui['crumbs'])}">
        <a href="{index_path(lang)}">{E(ui['crumb_home'])}</a> <span aria-hidden="true">/</span>
        <span aria-current="page">{E(tag_name(tag, lang))}</span>
      </nav>
'''

    ld = {
        "@context": "https://schema.org",
        "@graph": [
            {"@type": "Blog", "@id": f"{ORIGIN}/#blog", "name": ui['site_name'], "url": ORIGIN + '/',
             "description": ui['index_desc'], "inLanguage": [UI[l]['html_lang'] for l in LANGS],
             "author": {"@id": f"{MAIN}/#person"}, "publisher": {"@id": f"{MAIN}/#business"}},
            {"@type": "CollectionPage", "@id": ORIGIN + path, "url": ORIGIN + path, "name": title,
             "description": desc, "inLanguage": ui['html_lang'], "isPartOf": {"@id": f"{ORIGIN}/#blog"},
             "hasPart": [{"@id": p.url} for p in posts]},
        ],
    }

    return (head(lang, title, desc, path, alternates=alternates)
            + header(lang, switch)
            + f'''
  <section class="section page-head blog-head">
    <div class="wrap">
{crumbs}      <h1>{E(h1)}</h1>
      <p class="lede">{E(ui['tagline'] if not tag else (TAG_INTRO.get(tag, {}).get(lang) or f"{ui['posts_tagged']} {tag_name(tag, lang)}."))}</p>
    </div>
  </section>

  <section class="section blog-index">
    <div class="wrap blog-index-inner">
      <ul class="post-list">
{cards}
      </ul>
      <aside class="related blog-side">
        <h3>{E(ui['tags_h'])}</h3>
        <ul class="tag-list">
{tag_links}
        </ul>
        <p class="side-feed"><a href="{feed_path(lang)}">{E(ui['feed'])}</a></p>
      </aside>
    </div>
  </section>
'''
            + footer(lang, ld))


def render_post(p):
    lang, ui = p.lang, UI[p.lang]
    other = [l for l in LANGS if l != lang][0]
    alternates = {lang: p.path}
    if p.sibling:
        alternates[other] = p.sibling.path
        switch = (ui['switch_label'], p.sibling.path)
    else:
        switch = (ui['switch_missing'], None)

    updated = ''
    if p.updated and p.updated != p.date:
        updated = f' · <span>{ui["updated"]} <time datetime="{p.updated.isoformat()}">{fmt_date(p.updated, lang)}</time></span>'

    sibling_note = ''
    if p.sibling:
        note = {'en': 'Ook beschikbaar in het Nederlands:', 'nl': 'Also available in English:'}[lang]
        sibling_note = f'''      <p class="post-alt" lang="{other}"><a href="{p.sibling.path}" hreflang="{other}">{note} {E(p.sibling.title)}</a></p>
'''

    ld = {
        "@context": "https://schema.org",
        "@graph": [
            {"@type": "BlogPosting", "@id": p.url + '#post', "headline": p.title,
             "description": p.description, "url": p.url, "mainEntityOfPage": {"@id": p.url},
             "datePublished": p.date.isoformat(), "dateModified": (p.updated or p.date).isoformat(),
             "inLanguage": ui['html_lang'], "image": p.image_url,
             "keywords": [tag_name(t, lang) for t in p.tags],
             "wordCount": len(re.findall(r'\w+', p.body_md)),
             "author": {"@type": "Person", "@id": f"{MAIN}/#person", "name": AUTHOR, "url": MAIN + '/'},
             "publisher": {"@id": f"{MAIN}/#business"},
             "isPartOf": {"@id": f"{ORIGIN}/#blog"}},
            {"@type": "BreadcrumbList", "@id": p.url + '#breadcrumb', "itemListElement": [
                {"@type": "ListItem", "position": 1, "name": ui['crumb_home'], "item": ORIGIN + index_path(lang)},
                {"@type": "ListItem", "position": 2, "name": p.title}]},
        ],
    }
    if p.sibling:
        ld['@graph'][0]['workTranslation' if lang == LANGS[0] else 'translationOfWork'] = {"@id": p.sibling.url + '#post'}

    extra = f'''<meta property="article:published_time" content="{p.date.isoformat()}">
<meta property="article:modified_time" content="{(p.updated or p.date).isoformat()}">
<meta property="article:author" content="{MAIN}/">''' + ''.join(
        f'\n<meta property="article:tag" content="{E(tag_name(t, lang))}">' for t in p.tags)

    return (head(lang, f'{p.title} — {ui["site_name"]}', p.description, p.path,
                 alternates=alternates, og_type='article', image=p.image_url, extra=extra)
            + header(lang, switch)
            + f'''
  <article class="post">
    <header class="section page-head post-head">
      <div class="wrap wrap-narrow">
        <nav class="crumbs" aria-label="{E(ui['crumbs'])}">
          <a href="{index_path(lang)}">{E(ui['crumb_home'])}</a> <span aria-hidden="true">/</span>
          <span aria-current="page">{E(p.title)}</span>
        </nav>
        <h1>{E(p.title)}</h1>
        <p class="lede">{E(p.description)}</p>
        <p class="post-meta">
          <span>{ui['by']} <a href="{MAIN}/#about" rel="author">{AUTHOR}</a></span>
          · <span>{ui['published']} <time datetime="{p.date.isoformat()}">{fmt_date(p.date, lang)}</time></span>{updated}
          · <span>{p.minutes} {ui['read']}</span>
        </p>
        <p class="post-tags">{tag_chips(p, lang)}</p>
{sibling_note}      </div>
    </header>

    <div class="section post-body">
      <div class="wrap wrap-narrow prose">
{p.html}
      </div>
    </div>

    <footer class="section section-alt post-foot">
      <div class="wrap wrap-narrow">
        <div class="author-card">
          <p class="eyebrow">{E(ui['about_h'])}</p>
          <p>{E(ui['about'])}</p>
          <div class="hero-actions">
            <a class="btn btn-primary" href="{MAIN}/">codeverse.nl</a>
            <a class="btn btn-ghost" href="{index_path(lang)}">{E(ui['back'])}</a>
          </div>
        </div>
      </div>
    </footer>
  </article>
'''
            + footer(lang, ld))


def render_404():
    lang, ui = LANGS[0], UI[LANGS[0]]
    ld = {"@context": "https://schema.org", "@type": "WebPage", "name": ui['not_found'], "isPartOf": {"@id": f"{ORIGIN}/#blog"}}
    return (head(lang, f'{ui["not_found"]} — {ui["site_name"]}', ui['not_found_lede'], '/404.html',
                 alternates={}, robots='noindex, follow')
            + header(lang, (UI[lang]['switch_label'], index_path('nl')))
            + f'''
  <section class="section error-page">
    <div class="wrap">
      <p class="error-code" aria-hidden="true">404</p>
      <h1>{E(ui['not_found'])}</h1>
      <p class="lede">{E(ui['not_found_lede'])}</p>
      <p class="lede" lang="nl">{E(UI['nl']['not_found_lede'])}</p>
      <div class="hero-actions">
        <a class="btn btn-primary" href="/">{E(ui['all_posts'])}</a>
        <a class="btn btn-ghost" href="/nl/">{E(UI['nl']['all_posts'])}</a>
      </div>
    </div>
  </section>
'''
            + footer(lang, ld))


# ----------------------------------------------------------------------------
# Feeds, sitemap, robots, headers
# ----------------------------------------------------------------------------

def rfc822(d):
    return dt.datetime.combine(d, dt.time(9, 0), tzinfo=TZ).strftime('%a, %d %b %Y %H:%M:%S %z')


def render_feed(lang, posts):
    ui = UI[lang]
    items = []
    for p in posts[:20]:
        cats = ''.join(f'\n      <category>{E(tag_name(t, lang))}</category>' for t in p.tags)
        items.append(f'''    <item>
      <title>{E(p.title)}</title>
      <link>{p.url}</link>
      <guid isPermaLink="true">{p.url}</guid>
      <pubDate>{rfc822(p.date)}</pubDate>
      <description>{E(p.description)}</description>{cats}
      <content:encoded><![CDATA[{p.html.replace(']]>', ']]]]><![CDATA[>')}]]></content:encoded>
    </item>''')
    last = rfc822(posts[0].date) if posts else rfc822(dt.date.today())
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom" xmlns:content="http://purl.org/rss/1.0/modules/content/">
  <channel>
    <title>{E(ui['site_name'])} ({ui['lang_name']})</title>
    <link>{ORIGIN}{index_path(lang)}</link>
    <atom:link href="{ORIGIN}{feed_path(lang)}" rel="self" type="application/rss+xml"/>
    <description>{E(ui['index_desc'])}</description>
    <language>{ui['html_lang']}</language>
    <lastBuildDate>{last}</lastBuildDate>
{chr(10).join(items)}
  </channel>
</rss>
'''


def render_sitemap(posts, tags_by_lang):
    def entry(paths, lastmod=None, prio='0.6', freq='monthly'):
        alts = ''.join(f'\n    <xhtml:link rel="alternate" hreflang="{l}" href="{ORIGIN}{q}"/>' for l, q in sorted(paths.items()))
        if LANGS[0] in paths:
            alts += f'\n    <xhtml:link rel="alternate" hreflang="x-default" href="{ORIGIN}{paths[LANGS[0]]}"/>'
        lm = f'\n    <lastmod>{lastmod}</lastmod>' if lastmod else ''
        out = []
        for l, q in sorted(paths.items()):
            out.append(f'''  <url>
    <loc>{ORIGIN}{q}</loc>{lm}{alts}
    <changefreq>{freq}</changefreq>
    <priority>{prio}</priority>
  </url>''')
        return '\n'.join(out)

    blocks = [entry({l: index_path(l) for l in LANGS},
                    lastmod=posts[0].date.isoformat() if posts else None, prio='1.0', freq='weekly')]
    seen = set()
    for p in posts:
        if p.slug in seen:
            continue
        seen.add(p.slug)
        group = {p.lang: p.path}
        if p.sibling:
            group[p.sibling.lang] = p.sibling.path
        lastmod = max([(q.updated or q.date) for q in ([p] + ([p.sibling] if p.sibling else []))])
        blocks.append(entry(group, lastmod=lastmod.isoformat(), prio='0.8'))
    all_tags = sorted({t for l in LANGS for t in tags_by_lang[l]})
    for t in all_tags:
        blocks.append(entry({l: tag_path(l, t) for l in LANGS if t in tags_by_lang[l]}, prio='0.4'))
    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:xhtml="http://www.w3.org/1999/xhtml">\n'
            + '\n'.join(blocks) + '\n</urlset>\n')


ROBOTS = f'''User-agent: *
Allow: /

Sitemap: {ORIGIN}/sitemap.xml
'''

HAS_TAG = {l: set() for l in LANGS}   # filled in main(); the header only links tag pages that exist

LD_BLOCK = re.compile(r'<script type="application/ld\+json">(.*?)</script>', re.S)


def render_headers(out):
    """Same policy as the main site. The inline JSON-LD blocks are allow-listed by
    hash, so this runs last, over the pages just written."""
    hashes = set()
    for path in glob.glob(os.path.join(out, '**', '*.html'), recursive=True):
        for m in LD_BLOCK.finditer(io.open(path, encoding='utf-8').read()):
            json.loads(m.group(1))
            hashes.add('sha256-' + base64.b64encode(hashlib.sha256(m.group(1).encode('utf-8')).digest()).decode())
    joined = ' '.join(f"'{h}'" for h in sorted(hashes))
    return f'''# Cloudflare Pages headers — generated by tools/build-blog.py, do not edit by hand.
# Inline JSON-LD blocks are allow-listed by SHA-256 so script-src stays strict.

/*
  Content-Security-Policy: default-src 'self'; script-src 'self' {joined}; style-src 'self'; img-src 'self' data:; font-src 'self'; connect-src 'self'; form-action 'none'; frame-ancestors 'none'; base-uri 'self'; object-src 'none'; upgrade-insecure-requests
  Strict-Transport-Security: max-age=31536000; includeSubDomains; preload
  X-Content-Type-Options: nosniff
  Referrer-Policy: strict-origin-when-cross-origin
  Permissions-Policy: geolocation=(), microphone=(), camera=(), interest-cohort=()
  Cross-Origin-Opener-Policy: same-origin

/assets/*
  Cache-Control: public, max-age=3600

/*.jpg
  Cache-Control: public, max-age=86400
/*.jpeg
  Cache-Control: public, max-age=86400
/*.png
  Cache-Control: public, max-age=86400
/*.webp
  Cache-Control: public, max-age=86400

/feed.xml
  Content-Type: application/rss+xml; charset=utf-8
  Cache-Control: public, max-age=3600
/nl/feed.xml
  Content-Type: application/rss+xml; charset=utf-8
  Cache-Control: public, max-age=3600
'''


# ----------------------------------------------------------------------------
# Markdown -> HTML (small, deliberate subset)
# ----------------------------------------------------------------------------

def slugify(text):
    s = re.sub(r'[^a-z0-9]+', '-', text.lower()).strip('-')
    return s or 'section'


def inline(text, base):
    """Inline markup. Escapes HTML first, so raw tags in running text are shown literally."""
    # protect code spans
    codes = []

    def keep(m):
        codes.append(E(m.group(2)))
        return f'\x00{len(codes) - 1}\x00'
    text = re.sub(r'(`+)(.+?)\1', keep, text)
    text = E(text, quote=False)

    def fix_src(src):
        src = src.strip()
        if re.match(r'^(https?:|mailto:|/|#)', src):
            return src
        return base + src.lstrip('./')

    # images
    text = re.sub(r'!\[([^\]]*)\]\(([^)\s]+)(?:\s+"([^"]*)")?\)',
                  lambda m: f'<img src="{E(fix_src(m.group(2)))}" alt="{m.group(1)}" loading="lazy">', text)
    # links
    text = re.sub(r'\[([^\]]+)\]\(([^)\s]+)(?:\s+"([^"]*)")?\)',
                  lambda m: f'<a href="{E(fix_src(m.group(2)))}"'
                            + (f' title="{m.group(3)}"' if m.group(3) else '')
                            + (' rel="noopener"' if m.group(2).startswith('http') and HOST not in m.group(2) else '')
                            + f'>{m.group(1)}</a>', text)
    # autolinks
    text = re.sub(r'&lt;(https?://[^\s&]+)&gt;', r'<a href="\1" rel="noopener">\1</a>', text)
    text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
    text = re.sub(r'(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])', r'<em>\1</em>', text)
    text = re.sub(r'(?<!\w)_(?!\s)(.+?)(?<!\s)_(?!\w)', r'<em>\1</em>', text)
    text = re.sub(r'~~(.+?)~~', r'<del>\1</del>', text)
    text = text.replace(' -- ', ' — ')
    text = re.sub(r'\x00(\d+)\x00', lambda m: f'<code>{codes[int(m.group(1))]}</code>', text)
    return text


def md_to_html(src, base):
    # HTML comments are author notes, never shipped. A comment on a line of its own takes the
    # line with it, so a note between two lines of a paragraph does not split the paragraph.
    src = re.sub(r'^[ \t]*<!--.*?-->[ \t]*\n', '', src, flags=re.S | re.M)
    src = re.sub(r'[ \t]*<!--.*?-->', '', src, flags=re.S)
    lines = src.replace('\r\n', '\n').split('\n')
    out, i, n = [], 0, len(lines)
    used_ids = set()

    def close_para(buf):
        if buf:
            para = ' '.join(s.strip() for s in buf)
            # a paragraph that is only an image becomes a figure, caption from the title
            m = re.fullmatch(r'!\[([^\]]*)\]\(([^)\s]+)(?:\s+"([^"]*)")?\)', para.strip())
            if m:
                img = inline(para, base)
                cap = f'<figcaption>{inline(m.group(3), base)}</figcaption>' if m.group(3) else ''
                out.append(f'<figure>{img}{cap}</figure>')
            else:
                out.append(f'<p>{inline(para, base)}</p>')
            buf.clear()

    para = []
    while i < n:
        line = lines[i]
        stripped = line.strip()

        if not stripped:
            close_para(para); i += 1; continue

        # fenced code
        m = re.match(r'^```\s*(\S+)?\s*$', stripped)
        if m:
            close_para(para)
            lang = m.group(1)
            buf = []
            i += 1
            while i < n and not lines[i].strip().startswith('```'):
                buf.append(lines[i]); i += 1
            i += 1
            cls = f' class="language-{E(lang)}"' if lang else ''
            out.append(f'<pre><code{cls}>{E(chr(10).join(buf))}</code></pre>')
            continue

        # raw HTML block: starts with a tag on its own line, runs to the next blank line
        if re.match(r'^<(?:div|details|summary|figure|video|iframe|table|aside|section|p|ul|ol|blockquote|hr|h[1-6])\b', stripped):
            close_para(para)
            buf = []
            while i < n and lines[i].strip():
                buf.append(lines[i]); i += 1
            out.append('\n'.join(buf))
            continue

        # heading
        m = re.match(r'^(#{1,6})\s+(.+?)\s*#*\s*$', stripped)
        if m:
            close_para(para)
            level = min(max(len(m.group(1)), 2), 6)  # '#' and '##' both become h2: the page h1 is the title
            text = m.group(2)
            hid = slugify(re.sub(r'[`*_\[\]()]', '', text))
            base_id, k = hid, 2
            while hid in used_ids:
                hid = f'{base_id}-{k}'; k += 1
            used_ids.add(hid)
            out.append(f'<h{level} id="{hid}">{inline(text, base)}<a class="anchor" href="#{hid}" aria-hidden="true" tabindex="-1">#</a></h{level}>')
            i += 1; continue

        # horizontal rule
        if re.fullmatch(r'(?:-{3,}|\*{3,}|_{3,})', stripped):
            close_para(para); out.append('<hr>'); i += 1; continue

        # blockquote
        if stripped.startswith('>'):
            close_para(para)
            buf = []
            while i < n and lines[i].strip().startswith('>'):
                buf.append(re.sub(r'^\s*>\s?', '', lines[i])); i += 1
            out.append(f'<blockquote>{md_to_html(chr(10).join(buf), base)}</blockquote>')
            continue

        # table
        if '|' in stripped and i + 1 < n and re.fullmatch(r'\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)*\|?\s*', lines[i + 1]):
            close_para(para)
            def cells(row):
                row = row.strip()
                if row.startswith('|'): row = row[1:]
                if row.endswith('|'): row = row[:-1]
                return [c.strip() for c in row.split('|')]
            aligns = []
            for c in cells(lines[i + 1]):
                aligns.append('right' if c.endswith(':') and not c.startswith(':') else
                              'center' if c.startswith(':') and c.endswith(':') else None)
            head_cells = cells(line)
            i += 2
            rows = []
            while i < n and '|' in lines[i] and lines[i].strip():
                rows.append(cells(lines[i])); i += 1
            def td(tag, vals):
                return ''.join(
                    f'<{tag}{" style=\"text-align:" + aligns[j] + "\"" if j < len(aligns) and aligns[j] else ""}>{inline(v, base)}</{tag}>'
                    for j, v in enumerate(vals))
            body = ''.join(f'<tr>{td("td", r)}</tr>' for r in rows)
            out.append(f'<div class="table-wrap"><table><thead><tr>{td("th", head_cells)}</tr></thead><tbody>{body}</tbody></table></div>')
            continue

        # lists (one level of nesting via indentation)
        m = re.match(r'^(\s*)([-*+]|\d+[.)])\s+(.*)$', line)
        if m:
            close_para(para)
            block, i = parse_list(lines, i, base)
            out.append(block)
            continue

        para.append(line)
        i += 1

    close_para(para)
    return '\n'.join(out)


def parse_list(lines, i, base):
    """Parse a (possibly nested) list starting at lines[i]. Returns (html, next line index)."""
    n = len(lines)
    first = re.match(r'^(\s*)([-*+]|\d+[.)])\s+', lines[i])
    indent = len(first.group(1))
    ordered = first.group(2)[0].isdigit()
    items = []  # each item: [text lines, nested raw lines]
    while i < n:
        line = lines[i]
        if not line.strip():
            # blank line: list continues only if the next non-blank line is still part of it
            j = i + 1
            while j < n and not lines[j].strip():
                j += 1
            if j < n and (re.match(r'^(\s*)([-*+]|\d+[.)])\s+', lines[j]) and len(re.match(r'^(\s*)', lines[j]).group(1)) >= indent
                          or len(re.match(r'^(\s*)', lines[j]).group(1)) > indent):
                if items and len(re.match(r'^(\s*)', lines[j]).group(1)) > indent:
                    items[-1][1].append('')
                i = j
                continue
            break
        m = re.match(r'^(\s*)([-*+]|\d+[.)])\s+(.*)$', line)
        cur_indent = len(re.match(r'^(\s*)', line).group(1))
        if m and cur_indent == indent and (m.group(2)[0].isdigit() == ordered):
            items.append([[m.group(3)], []])
        elif cur_indent > indent and items:
            if not m and not items[-1][1]:
                items[-1][0].append(line.strip())   # wrapped item text, not a nested block
            else:
                items[-1][1].append(line[indent + 2:] if len(line) > indent + 2 else line.strip())
        elif m and cur_indent < indent:
            break
        elif not m and cur_indent >= indent and items and not items[-1][1]:
            items[-1][0].append(line.strip())      # lazy continuation of the item text
        else:
            break
        i += 1
    end = i

    html_items = []
    for text, nested in items:
        body = inline(' '.join(text), base)
        task = re.match(r'^\[( |x|X)\]\s+(.*)$', ' '.join(text))
        if task:
            body = (f'<input type="checkbox" disabled{" checked" if task.group(1).lower() == "x" else ""}> '
                    + inline(task.group(2), base))
        if nested:
            body += '\n' + md_to_html('\n'.join(nested), base)
        html_items.append(f'<li>{body}</li>')
    tag = 'ol' if ordered else 'ul'
    return f'<{tag}>\n' + '\n'.join(html_items) + f'\n</{tag}>', end


# ----------------------------------------------------------------------------
# Build
# ----------------------------------------------------------------------------

def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    io.open(path, 'w', encoding='utf-8').write(text)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--drafts', action='store_true', help='include posts marked draft: true')
    ap.add_argument('--out', default=OUT_DEFAULT, help='output directory (default: blog/)')
    args = ap.parse_args()
    out = os.path.abspath(args.out)

    posts = load_posts(args.drafts)
    by_lang = {l: [p for p in posts if p.lang == l] for l in LANGS}
    tags_by_lang = {l: sorted({t for p in by_lang[l] for t in p.tags}) for l in LANGS}
    for l in LANGS:
        HAS_TAG[l] = set(tags_by_lang[l])

    # every relative image a post mentions must exist next to it
    for p in posts:
        body = re.sub(r'<!--.*?-->', '', p.body_md, flags=re.S)
        refs = re.findall(r'!\[[^\]]*\]\(([^)\s]+)', body) + ([p.image] if p.image else [])
        for r in refs:
            if not re.match(r'^(https?:|/)', r) and not os.path.exists(os.path.join(POSTS, p.slug, r.lstrip('./'))):
                print(f'WARNING posts/{p.slug}/{p.lang}.md references missing image {r}')

    # start clean, but only remove what we generate (keeps the dir safe to point at)
    if os.path.isdir(out):
        for name in os.listdir(out):
            p = os.path.join(out, name)
            shutil.rmtree(p) if os.path.isdir(p) else os.remove(p)
    os.makedirs(out, exist_ok=True)

    # shared assets from the main site, plus the blog stylesheet
    os.makedirs(os.path.join(out, 'assets', 'css'), exist_ok=True)
    os.makedirs(os.path.join(out, 'assets', 'js'), exist_ok=True)
    os.makedirs(os.path.join(out, 'assets', 'img'), exist_ok=True)
    shutil.copy(os.path.join(SITE, 'assets', 'css', 'style.css'), os.path.join(out, 'assets', 'css', 'style.css'))
    shutil.copy(os.path.join(ROOT, 'tools', 'blog.css'), os.path.join(out, 'assets', 'css', 'blog.css'))
    shutil.copy(os.path.join(SITE, 'assets', 'js', 'main.js'), os.path.join(out, 'assets', 'js', 'main.js'))
    shutil.copy(os.path.join(SITE, 'assets', 'img', 'og.png'), os.path.join(out, 'assets', 'img', 'og.png'))
    for f in ('favicon.svg', 'favicon.ico'):
        shutil.copy(os.path.join(SITE, f), os.path.join(out, f))

    # posts + their images
    for p in posts:
        write(os.path.join(out, p.path.lstrip('/'), 'index.html'), render_post(p))
        src_dir = os.path.join(POSTS, p.slug)
        for f in os.listdir(src_dir):
            if not f.endswith('.md') and os.path.isfile(os.path.join(src_dir, f)):
                shutil.copy(os.path.join(src_dir, f), os.path.join(out, p.slug, f))

    # indexes, tag pages, feeds
    for l in LANGS:
        write(os.path.join(out, index_path(l).lstrip('/'), 'index.html'), render_list(l, by_lang[l], by_lang))
        for t in tags_by_lang[l]:
            write(os.path.join(out, tag_path(l, t).lstrip('/'), 'index.html'),
                  render_list(l, [p for p in by_lang[l] if t in p.tags], by_lang, tag=t))
        write(os.path.join(out, feed_path(l).lstrip('/')), render_feed(l, by_lang[l]))

    write(os.path.join(out, '404.html'), render_404())
    write(os.path.join(out, 'sitemap.xml'), render_sitemap(posts, tags_by_lang))
    write(os.path.join(out, 'robots.txt'), ROBOTS)
    write(os.path.join(out, f'{INDEXNOW_KEY}.txt'), INDEXNOW_KEY)   # IndexNow key verification file
    write(os.path.join(out, '_headers'), render_headers(out))

    drafts = ' (including drafts — do NOT deploy this output)' if args.drafts else ''
    print(f'{len(posts)} post page(s) ({len({p.slug for p in posts})} post(s)) -> {out}{drafts}')
    for p in posts:
        print(f'  {p.path:45s} {p.date}  {p.title}')


if __name__ == '__main__':
    main()
