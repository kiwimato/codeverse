# codeverse.nl — freelance site

The Codeverse business site. Lives in [`site/`](site/). Plain semantic HTML, hand-written
CSS and ~90 lines of vanilla JS — no framework, no build step, no external requests
(system fonts, so nothing is fetched from a Google Fonts CDN, which also keeps the site
trivially clean under GDPR).

The blog at `blog.codeverse.nl` lives in this repo too (see "The blog" below). The CV and
the old Pillar CV page (`resume.dacia.ninja`) live in the separate private `my-resume` repo.
This repo holds nothing private: the contact address on the site is a disposable alias.

```
site/
├── index.html                    homepage: hero, services, approach, engagements,
│                                 stack, about, where-I-work + FAQ, contact
├── 404.html                      real 404 — without it Pages soft-404s every bad URL
├── aws-cloud-consultant/         ┐
├── terraform-consultant/         │
├── cicd-devops-engineer/         ├ six service pages, one per search intent
├── cloud-security-hardening/     │  (generated — see tools/ below)
├── observability-monitoring/     │
├── network-engineering/          ┘
├── _headers                      Cloudflare Pages security + cache headers
├── robots.txt
├── sitemap.xml
├── favicon.svg / .ico
└── assets/
    ├── css/style.css             tokens, light + dark via prefers-color-scheme
    ├── js/main.js                mobile nav, footer year, contact-address assembly
    └── img/og.png                1200x630 social preview card

posts/                            blog sources (Markdown, EN + NL) — see "The blog" below
blog/                             generated blog, deploy root for blog.codeverse.nl

tools/
├── build-service-pages.py        source of truth for the six service pages
├── build-blog.py                 Markdown -> blog/ (zero dependencies)
├── blog.css                      blog-only styles, layered on site/assets/css/style.css
├── refresh-csp.py                re-derives the CSP hash allow-list in _headers
├── indexnow.py                   ping IndexNow with every URL in a live sitemap
├── strip-exif.py                 remove EXIF/GPS from photos before they go into a post
└── og-image.html                 source for og.png
```

None of `tools/` is deployed — only `site/` is uploaded.

## Regenerating

The homepage is hand-maintained. The six service pages are not: their copy lives in the
`PAGES` list in `tools/build-service-pages.py`, and editing `site/<slug>/index.html`
directly works until the next run overwrites it.

```bash
python3 tools/build-service-pages.py   # rewrite the six service pages
python3 tools/refresh-csp.py           # ALWAYS run after — see below
```

`refresh-csp.py` is not optional. The CSP allow-lists each page's inline JSON-LD by
SHA-256 rather than using `'unsafe-inline'`, so any change to a page's structured data
invalidates its hash. Get this wrong and the browser silently drops the JSON-LD — the page
still looks fine, and the rich results quietly stop working.


---

## The contact address

The site never puts `your personal mailbox` on the page, and never puts any address in the
served HTML at all. Two things are going on:

**1. A dedicated, disposable alias.** The page advertises `hello@codeverse.nl`, not your
real mailbox. Because `codeverse.nl` MX already points at Google Workspace
(`aspmx.l.google.com`, see `../terraform/cloudflare_codeverse.nl.tf`), the cheapest way to
create it is a **Google Group**, not a user alias:

* Admin console → Directory → Groups → Create group
* Name `hello`, address `hello@codeverse.nl`
* Access type **Public** → "Who can post: Anyone on the internet" (external senders must
  be able to reach it, otherwise enquiries bounce)
* Members: just `your personal mailbox`

A Group beats a user alias here because it is free, does not touch your account, and can
be **deleted and recreated in seconds** if the address ever gets scraped into a spam list —
your real address never has to change.

**2. Filterable on arrival.** Two independent signals:

| Signal | Where it comes from | Gmail filter |
| --- | --- | --- |
| `Delivered-To: hello@codeverse.nl` | the Group | `deliveredto:hello@codeverse.nl` |
| Subject `Enquiry via codeverse.nl` | `mailto:` on the page prefills it | `subject:"Enquiry via codeverse.nl"` |

`deliveredto:` is the reliable one — spammers routinely forge `To:`, but they cannot forge
which alias actually accepted the message. Suggested filter: label `Codeverse/Web`, never
send to spam, mark important. The subject prefill is a bonus that separates people who used
the button from people who typed the address by hand (i.e. from a scrape).

**One alias per channel** is worth doing: `hello@` on the website, something else on
LinkedIn, something else on the CV PDF. When one of them starts attracting spam you know
exactly which channel leaked, and you delete only that Group.

### Changing the advertised address

It is stored base64-encoded and split into two halves in `site/assets/js/main.js`, so
neither the address nor a single decodable blob appears anywhere in the source. Crawlers
that parse markup — which is nearly all of them — get nothing; only a browser that runs
the script sees it.

```bash
echo -n 'newalias'    | base64   # -> LOCAL
echo -n 'codeverse.nl' | base64   # -> DOMAIN
```

Paste both into the `LOCAL` / `DOMAIN` constants near the bottom of `main.js` and redeploy.

This is obfuscation, not security — anyone reading `main.js` can decode it in a second.
That is exactly why the address behind it should stay a disposable alias.

---

## Local preview

```bash
python3 -m http.server 8000 --directory site
# http://127.0.0.1:8000/
```

Serve `site/` as the document root, not the repo root — every asset path is absolute
(`/assets/...`), matching how Pages will serve it.

## Deploy

Infrastructure is in `../terraform`. Two new files:

* `cloudflare_pages_codeverse.tf` — the `codeverse` Pages project + apex and www domain bindings
* `cloudflare_codeverse.nl.tf` — apex and `www` now CNAME to `<project>.pages.dev` (proxied)

```bash
cd ../terraform
terraform plan -out=apply.tfplan     # review — see the note below
terraform apply apply.tfplan
```

> **Read the plan carefully the first time.** The apex record changes from `A` (the ocean
> droplet) to `CNAME` (Pages). Terraform cannot change a record type in place, so it shows
> a **destroy then create** — a few seconds with no apex record. The droplet was only
> serving the placeholder `hello, lil hooman :)`, so nothing real is being cut over, and
> `resume.codeverse.nl` still points at ocean and is not touched.

Then push the assets (same direct-upload pattern as `dvrbridge` and `omenie`):

```bash
wrangler pages deploy ~/code/codeverse/site --project-name=codeverse --branch=main
```

`_headers` is picked up automatically from the deploy root — CSP, HSTS, `nosniff`,
`frame-ancestors 'none'`, `Permissions-Policy`, and cache rules.

> The CSP allow-lists the one inline `<script>` (the JSON-LD block) **by SHA-256 hash**
> rather than with `'unsafe-inline'`. If you edit the JSON-LD, regenerate the hash — the
> exact command is in a comment at the top of `site/_headers`.

## Social card

`site/assets/img/og.png` is generated from `tools/og-image.html` (which is deliberately
outside `site/`, so it never ships). Regenerate after editing it:

```bash
python3 -m http.server 8732 &
firefox --headless --screenshot "$PWD/site/assets/img/og.png" \
        --window-size=1200,630 http://127.0.0.1:8732/tools/og-image.html
```

---

## SEO

### Two things that were actively broken

Both were found by checking the deployed site rather than the source, and both are fixed
in `site/`:

* **`www` served a second copy.** Pages answers on both custom domains, so
  `www.codeverse.nl` returned `200` for every page — a full duplicate of the site. The
  canonical tag pointed at the apex, which is a hint Google may ignore, not a rule.
  Fixed with a zone-level redirect rule in `../terraform/cloudflare_redirect_codeverse.tf`.

  > My first attempt at this used a `_redirects` file with an absolute `from` URL. That is
  > Netlify syntax — Pages matches `_redirects` on the **path** only, and both hostnames
  > are bound to the same project, so the rule silently never fired. The file deployed
  > cleanly and did nothing. A dynamic redirect rule runs at the edge before Pages, where
  > `http.host` is actually available.

  > The API token needs **Zone → Dynamic Redirect → Edit** on `codeverse.nl`. Without it
  > `terraform apply` fails on this resource alone with `Authentication error (10000)`
  > while every DNS and Pages resource applies fine — the token is valid, just not scoped
  > for the rulesets API.
* **Every unknown URL returned `200`.** With no `404.html`, Pages falls back to
  `index.html` — so `/anything-at-all` served the homepage with a success status. That is a
  soft-404, and it invites crawlers to index unlimited junk paths as homepage duplicates.
  `404.html` gives a real `404` and is `noindex`.

### Structure

Location and remote-work terms are carried by real page copy — a "Where I work" section
naming Utrecht, Amsterdam, Noord-Holland, Zuid-Holland, Flevoland, Gelderland and the
Randstad city by city, plus an explicit fully-remote block — rather than by stuffing.

The six service pages exist because one homepage cannot rank for six different intents.
Someone searching *freelance terraform consultant* and someone searching *AWS migration*
want different pages. Each one has distinct copy, its own `Service` + `WebPage` +
`BreadcrumbList` JSON-LD, a unique title and description, and is linked from the matching
card on the homepage with descriptive anchor text.

Also in place:

* JSON-LD `@graph` on the homepage: `ProfessionalService` (20 `areaServed` entries,
  `serviceType`, `hasOfferCatalog`), `Person`, `WebSite`, `FAQPage`
* The four FAQ answers are byte-identical between the visible `<details>` and the
  `FAQPage` schema — Google drops FAQ rich results when they diverge, so if you edit one,
  edit both
* Every title is under 62 characters and every description under 160, so neither gets
  truncated in results
* `geo.region` / `geo.position`, canonicals, `og:` and `twitter:` cards, sitemap, robots

### Deliberately not done

**Per-city landing pages** (`/devops-engineer-amsterdam/` and so on). For a one-person
consultancy there is no honest way to make fifteen of those meaningfully different from
each other, and near-duplicate location pages are exactly what Google's doorway-page
guidance targets — they get filtered out at best and hurt the whole domain at worst. The
"Where I work" copy plus `areaServed` covers local intent without that risk.

### Still yours to do

Add `https://codeverse.nl/` to the existing Google Search Console domain property and
submit `sitemap.xml`. The GSC verification TXT is already in Terraform and covers the whole
zone, so verification should pass immediately. Worth checking the Coverage report a week
later to confirm the soft-404 URLs have dropped out.

---

## The blog — blog.codeverse.nl

A separate Cloudflare Pages project (`codeverse-blog`) on its own subdomain, built from
Markdown by `tools/build-blog.py`. Zero dependencies, same visual system as the main site
(it copies `site/assets/css/style.css` and adds `tools/blog.css` on top), same strict CSP.

```
posts/                              SOURCE — never deployed
└── <slug>/
    ├── en.md                       -> https://blog.codeverse.nl/<slug>/
    ├── nl.md                       -> https://blog.codeverse.nl/nl/<slug>/
    └── *.jpg / *.png               photos, shared by both languages

blog/                               OUTPUT — the deploy root, fully regenerated each build
├── index.html  /nl/index.html      post lists (EN at the root, NL under /nl/)
├── <slug>/  /nl/<slug>/            one page per language, hreflang-linked
├── tag/<tag>/  /nl/tag/<tag>/      one page per topic; the two in the nav are `repair`
│                                   ("Repair corner") and `opensource` ("Open source")
├── feed.xml  /nl/feed.xml          RSS, one per language
├── sitemap.xml                     with xhtml:link language alternates
├── _headers                        generated — CSP hashes for the JSON-LD are computed here
└── 404.html, robots.txt, assets/, favicon.*
```

### Writing a post

Make `posts/<slug>/` (lowercase and dashes — it becomes the URL), write `en.md` and/or
`nl.md`, drop the photos next to them. A post may exist in one language only; the other
language's switcher then says so instead of linking to a 404.

```markdown
---
title: Fixing the broken aluminium rod on a Lovens Explorer bakfiets
description: One or two sentences — index, meta tags and the feed all use this.
date: 2026-09-20
updated: 2026-10-01          # optional
tags: repair, bakfiets       # optional; display names per language live in TAGS in build-blog.py
image: hero.jpg              # optional; social-card image, relative to the post dir
draft: true                  # optional; skipped unless --drafts is given
---

## Section heading            (# and ## both become h2 — the page h1 is the title)

Paragraphs, **bold**, *italic*, `code`, [links](https://…), lists, > quotes, --- rules,
```fenced code```, pipe tables, and ![alt](photo.jpg "This becomes the caption").
HTML comments <!-- like this --> are stripped, so use them for notes to yourself.
```

Images are referenced relative to the post directory and rewritten to absolute URLs, so
the same file serves both languages. The build warns about any image that does not exist.

### Categories

A category is just a tag. Three places in `tools/build-blog.py` control them:

* `TAGS` — the slug's display name per language. A slug with no entry renders as-is.
* `TAG_INTRO` — optional blurb, used as both the tag page's lede and its meta description.
  Without one the page falls back to a generic "Posts filed under X" line, which is weak
  for a category you actually want found.
* `NAV_TAGS` — slugs promoted to the site navigation, in order. Each needs a matching
  `nav_<slug>` label in `UI` for **both** languages, or the build raises `KeyError`. A tag
  with nothing published in a language is dropped from that language's nav automatically.

Current nav categories: `repair` (Repair corner / Reparatiehoek) and `opensource`
(Open source) — small tools published on GitHub, each fixing one specific problem.

```bash
python3 tools/build-blog.py                       # -> blog/, drafts excluded
python3 tools/build-blog.py --drafts --out /tmp/p # preview drafts elsewhere; never deploy that
python3 -m http.server 8000 --directory blog      # local preview
```

### Deploy

Infrastructure: `../terraform/cloudflare_pages_blog.tf` (project + custom domain) and the
`blog` CNAME in `../terraform/cloudflare_codeverse.nl.tf`. Plan and apply once, then:

```bash
python3 tools/build-blog.py
wrangler pages deploy ~/code/codeverse/blog --project-name=codeverse-blog --branch=main
```

Both are the same direct-upload pattern as the main site; nothing deploys on git push.

After a deploy that adds or changes URLs, ping IndexNow (Bing, Yandex, Seznam, Naver):

```bash
python3 tools/indexnow.py https://blog.codeverse.nl/sitemap.xml
python3 tools/indexnow.py https://codeverse.nl/sitemap.xml     # works for the main site too
```

The key (`733f7cbf…`) is the one codeverse.nl and dvrbridge already use; the blog build
writes the verification file into `blog/` on every run. Google ignores IndexNow — the blog
sitemap is submitted under the `codeverse.nl` domain property in Search Console (done
2026-09-20), which the zone-wide verification TXT covers.

### Renaming the subdomain

`HOST` at the top of `tools/build-blog.py`, the `domain` in `cloudflare_pages_blog.tf`,
the `name` of the CNAME record, and the three "Blog" nav links in the main site
(`site/index.html`, `NAV` in `tools/build-service-pages.py`). That is the whole list.

### Writing posts

The step-by-step authoring guide, content rules and supported Markdown are in
[`posts/AGENTS.md`](posts/AGENTS.md).

---

## Open items — need your input

1. **A photo of you.** The old CV's `assets/images/profile.jpg` (in the `my-resume` repo)
   is the **Pillar theme's stock demo headshot** — a photo of a stranger, never use it. I removed it rather than publish it as you, and
   the hero now uses a decorative `main.tf` card instead. If you want a portrait there,
   drop a square image at `site/assets/img/mihai.jpg` and swap the two blocks in the hero
   — the markup is already written and commented in place.
2. **KVK / BTW numbers.** Dutch B2B clients look for these. There is a commented-out
   footer block in `site/index.html` ready for them.
3. **Availability line.** The hero chip currently states location only. There is a comment
   above it with wording for "Available for new engagements" / "Booked until Q1 2027" if
   you want to signal availability.
4. **`resume.codeverse.nl`.** Still points at the ocean droplet and still serves the
   placeholder. Decide whether to point it at the old Pillar CV, redirect it to
   `codeverse.nl`, or drop the record.
