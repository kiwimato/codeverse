# AGENTS.md — codeverse

Source for two Cloudflare Pages sites. Nothing here deploys on `git push`; each site is
a direct upload with `wrangler pages deploy`, and DNS plus the Pages projects live in
`~/code/terraform`.

| Site | Source | Deploy root | Pages project | Guide |
| --- | --- | --- | --- | --- |
| codeverse.nl (freelance site) | `site/` (hand-written) + `tools/build-service-pages.py` | `site/` | `codeverse` | `README.md` |
| blog.codeverse.nl | `posts/` + `tools/build-blog.py` | `blog/` (generated, git-ignored) | `codeverse-blog` | `posts/AGENTS.md` |

The CV (`RESUME.md`, its PDF build) is **not** here. It lives in the private
`~/code/my-resume` repo because it carries Mihai's personal email and phone number.

## Ground rules

* **This repo holds nothing private and may be public.** Never add Mihai's personal
  email address, phone number, or anything from the CV header. The site advertises a
  disposable alias assembled at runtime by `site/assets/js/main.js`; see `README.md`.
* **Nothing invented.** No made-up figures, clients, dates, repair details or quotes.
  Site copy about Mihai's work must trace back to what he said or to the CV. Unknown
  facts get a `<!-- TODO -->` / `<!-- CONFIRM -->` comment, not a plausible guess.
* **Working language: English only.** Do not claim Dutch or Romanian as working
  languages. The blog being in English, Dutch and Romanian is content, not a language claim.
* **Never publish `assets/images/profile.jpg` from the old CV** — it is the Pillar
  theme's stock photo of a stranger. There is no real portrait yet.
* **Do not commit, push, deploy or `terraform apply` unasked.**
* **Zero dependencies.** Everything in `tools/` is standard-library Python 3. No pip
  packages, no frameworks, no build step for `site/`.

## The site: things that break silently

* `site/<slug>/index.html` for the six service pages is **generated**. Edit the
  `PAGES` list in `tools/build-service-pages.py`, then run it.
* After any change to a page's JSON-LD (including regenerating service pages), run
  `python3 tools/refresh-csp.py`. The CSP allow-lists inline JSON-LD by SHA-256; a stale
  hash makes the browser drop the structured data while the page still looks fine.
* The homepage FAQ answers must stay byte-identical to the `FAQPage` JSON-LD.
* `site/index.html` is hand-maintained, including the engagements list. When Mihai's
  role changes, update it to match `RESUME.md` in the my-resume repo.

## Deploy

```bash
# site
wrangler pages deploy ~/code/codeverse/site --project-name=codeverse --branch=main --commit-dirty=true
python3 tools/indexnow.py https://codeverse.nl/sitemap.xml

# blog
python3 tools/build-blog.py
wrangler pages deploy ~/code/codeverse/blog --project-name=codeverse-blog --branch=main --commit-dirty=true
python3 tools/indexnow.py https://blog.codeverse.nl/sitemap.xml
```

The blog build copies the site's stylesheet, script, favicons and social card out of
`site/`, so the two sites must stay in this one repo.
