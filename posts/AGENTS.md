# AGENTS.md — the blog (blog.codeverse.nl)

Instructions for anyone, human or agent, writing or changing posts. The deeper
reference is the `## The blog` section of `../README.md`; this file is the
working checklist.

## How it works

```
posts/<slug>/en.md        -> https://blog.codeverse.nl/<slug>/
posts/<slug>/nl.md        -> https://blog.codeverse.nl/nl/<slug>/
posts/<slug>/*.jpg|png    -> https://blog.codeverse.nl/<slug>/<file>   (shared by both languages)
tools/build-blog.py       the generator: Markdown -> HTML, feeds, sitemap, tag pages, _headers
tools/blog.css            blog-only styles, layered on the main site's site/assets/css/style.css
blog/                     OUTPUT. Wiped and rewritten on every build. Never edit it, never
                          put files in it — put them here in posts/ and rebuild.
```

* `posts/` is the only source. `blog/` is the Cloudflare Pages deploy root.
* Zero dependencies. The generator is plain Python 3 with its own small Markdown
  converter. Do not add a pip package or a framework; the main site has the same rule.
* English is the default language (root URLs, `x-default`). Dutch lives under `/nl/`.
  A post may exist in one language only; the other language's switcher then shows a
  disabled "not available" state instead of a dead link.
* The slug is the directory name and becomes the URL in both languages. Lowercase,
  digits and dashes only. It should read well in English; do not translate it for `nl`.
* The page `<h1>` is the front-matter `title`. Inside the body `#` and `##` both become
  `<h2>`, `###` becomes `<h3>`, and so on.

## Writing a post

1. `mkdir posts/<slug>/` and write `en.md`, then `nl.md` with the same sections in the
   same order. Translate meaning, not word for word; Dutch should read as written by a
   Dutch speaker, not as a machine translation.
2. Photos go next to the Markdown. Strip metadata first; phone photos carry GPS:

   ```bash
   python3 tools/strip-exif.py ~/Downloads/PXL_*.jpg posts/<slug>/
   ```

   Then give them meaningful names (`copper-sleeve.jpg`, not `pxl_2026...jpg`). Keep
   them under ~300 KB each; the page has no image pipeline.
3. Build with drafts to a scratch directory and look at it:

   ```bash
   python3 tools/build-blog.py --drafts --out /tmp/blog-preview
   python3 -m http.server 8000 --directory /tmp/blog-preview
   ```

   The build warns about any image a post references that is not in its directory.
4. Remove `draft: true` from both files, build for real, deploy, ping IndexNow:

   ```bash
   python3 tools/build-blog.py
   wrangler pages deploy ~/code/codeverse/blog --project-name=codeverse-blog --branch=main --commit-dirty=true
   python3 tools/indexnow.py https://blog.codeverse.nl/sitemap.xml
   ```

   Nothing deploys on `git push`. Google reads the sitemap on its own; it is already
   submitted in Search Console under the `codeverse.nl` domain property.

### Front matter

```markdown
---
title: Fixing a snapped aluminium tube on a Lovens Explorer with a piece of copper pipe
description: One or two sentences. Used on the index, in meta tags, the RSS feed and the social card.
date: 2026-09-20            # ISO date; also the sort key
updated: 2026-10-01         # optional; shown when it differs from date
tags: repair, bakfiets      # optional, comma-separated slugs; see Categories
image: copper-sleeve.jpg    # optional; social-card image, relative to the post directory
draft: true                 # optional; excluded from the build unless --drafts is given
---
```

`title`, `description` and `date` are required; the build stops without them. Keep
`description` under 160 characters so search results do not truncate it. `title` gets
" — Codeverse blog" appended in the browser tab, so shorter is better, but say what
the post is actually about.

### Markdown the converter understands

Paragraphs, `**bold**`, `*italic*`, `` `code` ``, `~~strike~~`, `[links](url)`, bare
`<https://…>` autolinks, `#`…`######` headings (with anchor links), `-`/`*`/`1.` lists
with one level of nesting and wrapped lines, `- [ ]` task lists, `> quotes`, `---`
rules, fenced code blocks with an optional language, pipe tables with `:---:` alignment,
and images. A paragraph that is only an image becomes a `<figure>`, and the image's
title becomes the caption:

```markdown
![Alt text for screen readers](copper-sleeve.jpg "This line is the visible caption")
```

Image and link paths that are not absolute are resolved against the post's own URL, so
`photo.jpg` works from both the English and the Dutch page. A literal ` -- ` becomes an
em dash. A block that starts with an HTML tag on its own line (`<details>`, `<div>`,
`<table>`, `<video>`, …) is passed through raw until the next blank line. HTML comments
are stripped and never reach the page; use them for notes to yourself.

Not supported: footnotes, definition lists, nested blockquotes inside lists, reference-
style links, inline HTML inside a paragraph (it is escaped and shown literally).

### Categories

A category is a tag. Three things in `tools/build-blog.py` control them:

* `TAGS` — slug to display name per language. Unknown slugs render as-is, so add new
  ones here with both an `en` and an `nl` name.
* `TAG_INTRO` — optional blurb per tag, used as the tag page's lede and meta
  description. Worth writing for any category that should rank.
* `NAV_TAGS` — tags promoted to the header navigation, in order. Each needs a
  `nav_<slug>` label in `UI` for both languages or the build fails with `KeyError`.
  A tag with nothing published in a language is dropped from that language's nav.

Current categories: `repair` (Repair corner / Reparatiehoek) and `opensource` are in
the nav; `bakfiets`, `cloud`, `homelab`, `notes` are plain tags.

## Rules for the content

* **Nothing invented.** Every fact — what broke, which part, measurements, prices,
  figures, what a tool does — comes from Mihai or from a source he points at (a repo's
  README, a photo). If something is unknown, leave a `<!-- CONFIRM: … -->` or
  `<!-- TODO: … -->` comment next to the sentence and keep `draft: true` until he
  answers. Do not fill a gap with a plausible guess and publish it.
* **First person, plain, specific.** It is Mihai writing about something he did. No
  marketing voice, no "in this comprehensive guide", no filler intro paragraphs. Say
  what broke, what was tried, what worked, what it cost, what you would do differently.
* **Safety caveats where they belong.** A repair post says what the fix is good for and
  what it is not (a splint on a tent pole, yes; on steering or brakes, no). Galvanic
  corrosion, load-bearing parts and the like get a sentence, not a lecture.
* **No personal contact details.** No email address or phone number anywhere in a
  post. The header's "Work with me" link goes to codeverse.nl, which handles that.
* **No invented links.** Only link to pages that exist. Internal links are
  root-relative (`/other-post/`, `/nl/other-post/`).
* **Both languages or neither for facts.** If a detail changes in `en.md`, change it in
  `nl.md` in the same edit. The two files should stay parallel section for section.
* Dutch style: informal, direct, "je" not "u". Technical terms that Dutch engineers use
  in English stay in English (Terraform, pull request, pipeline); everyday words are
  Dutch (bakfiets, stang, huls, loodgieter).

## Changing the generator

`tools/build-blog.py` is one file: config and UI strings at the top, page templates in
the middle, the Markdown converter at the bottom. `HOST` is the only place the hostname
lives. Every page carries one inline JSON-LD `<script>` that the CSP allow-lists by
SHA-256; the build computes those hashes into `blog/_headers` on every run, so there is
nothing to refresh by hand. After touching the converter, build with `--drafts` and
check the existing posts still render; the list parser is the part that has broken
before (wrapped lines, nested lists).

Infrastructure for the subdomain is in `~/code/terraform/cloudflare_pages_blog.tf` and
the `blog` CNAME in `cloudflare_codeverse.nl.tf`. Renaming the subdomain means `HOST`,
those two Terraform resources, and the three "Blog" nav links in the main site.
