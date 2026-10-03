#!/usr/bin/env python3
"""Generate the per-service pages under site/<slug>/index.html.

These pages exist so codeverse.nl can rank for the distinct queries people
actually type ("freelance AWS consultant", "terraform consultant netherlands")
instead of asking one homepage to cover all of them. Each page is real,
specific copy — not the homepage reworded — because thin near-duplicate pages
get filtered out of the index rather than ranking.

THIS FILE IS THE SOURCE OF TRUTH for those six pages. Editing
site/<slug>/index.html directly works, but the next run of this script
overwrites it. The homepage (site/index.html) is hand-maintained and is never
touched here.

    python3 tools/build-service-pages.py        # from the repo root
"""
import html
import json
import os

SITE = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'site')
ORIGIN = 'https://codeverse.nl'

NAV = [('/#services', 'Services'), ('/#approach', 'Approach'), ('/#work', 'Engagements'),
       ('/#coverage', 'Where I work'), ('/#about', 'About'),
       ('https://blog.codeverse.nl/', 'Blog')]

PAGES = [
    dict(
        slug='aws-cloud-consultant',
        title='Freelance AWS Consultant — Architecture & Migration',
        desc='Freelance AWS consultant in Utrecht. Multi-account architecture, ECS and RDS workloads, and staged migration off legacy infrastructure. Remote or on-site.',
        h1='Freelance AWS consultant',
        service_name='AWS cloud architecture and migration',
        lede=('Most of the last decade of my work has been on AWS — for an online bank, an '
              'international leasing company and a manufacturing marketplace. What follows is '
              'the work I actually get called in for.'),
        takes_on=[
            ('Account and network layout', 'Multi-account structure, VPC and subnet design, '
             'segmentation, and the boring guardrails that stop an estate sprawling — so the '
             'thing is still comprehensible in two years.'),
            ('Workloads', 'ECS and EC2, RDS, S3, DynamoDB, API Gateway, CloudFront. Sizing, '
             'placement, autoscaling and the failure modes each one actually has.'),
            ('Migration off legacy', 'Moving estates from on-prem, from a single monolithic '
             'environment, or from a hosted provider onto AWS — in stages, with production '
             'running the whole time.'),
            ('Cost and availability', 'Finding where money is being burned on idle capacity, '
             'and where a single point of failure is quietly waiting for a bad Tuesday.'),
        ],
        how=[('Read the estate first',
              'Before anything moves, I map what is really running, what depends on what, and '
              'which parts nobody dares touch. Migration plans built from the architecture '
              'diagram rather than from reality are how weekends get ruined.'),
             ('Codify, then cut over',
              'The target gets built in Terraform before traffic goes anywhere near it. That '
              'makes the cutover reversible, and it means you are left with infrastructure your '
              'team can rebuild rather than a hand-made environment nobody understands.'),
             ('One environment at a time',
              'Staged migrations with a real rollback path. I have never needed a big-bang '
              'weekend cutover and would push back hard on one.')],
        proof=[('3D Hubs', 'Redesigned a monolithic infrastructure into isolated, reproducible '
                'environments on AWS with Terraform, so scaling and testing stopped fighting '
                'each other.'),
               ('LeasePlan', 'Ran SAP OpenText hosting on AWS where high availability was the '
                'hard requirement, and automated the instance configuration that had been manual.'),
               ('Knab', 'AWS work inside a regulated Dutch bank — ECS, RDS, CloudFront, API '
                'Gateway and DynamoDB, under the evidence requirements that come with financial '
                'services.')],
        fit=['You are on AWS already but it grew by hand and nobody can reproduce it.',
             'You are planning a migration and want someone who has done staged cutovers before.',
             'Your bill or your availability is telling you the architecture needs a rethink.',
             'You need AWS depth for a fixed period without hiring a permanent engineer.'],
        related=['terraform-consultant', 'cloud-security-hardening', 'observability-monitoring'],
    ),
    dict(
        slug='terraform-consultant',
        title='Freelance Terraform Consultant — Infrastructure as Code',
        desc='Freelance Terraform consultant in Utrecht. Module design, importing click-ops estates into state, and Ansible or Puppet underneath. Remote or on-site.',
        h1='Freelance Terraform consultant',
        service_name='Infrastructure as Code with Terraform',
        lede=('Terraform is the tool I reach for first, and has been across every engagement '
              'since 2018. The interesting problem is almost never the syntax — it is what to '
              'do with an estate that was built by hand and now has to become code.'),
        takes_on=[
            ('Bringing click-ops under control', 'Importing an existing, hand-built estate into '
             'state without a rebuild. This is the messy one, and the one most teams stall on.'),
            ('Module design', 'A module library your team can actually use: sensible interfaces, '
             'versioned, documented, and not so abstract that reading it is harder than reading '
             'the resources.'),
            ('State strategy', 'Backends, workspace and environment layout, locking, and blast '
             'radius — so a mistake in staging cannot reach into production.'),
            ('The layer underneath', 'Ansible or Puppet for configuration management where '
             'Terraform stops. Both have been production tools for me, not weekend reading.'),
        ],
        how=[('Small, reviewable changes',
              'Infrastructure changes should go through review like any other code, and a plan '
              'should be readable by someone who did not write it. If a plan output needs '
              'explaining every time, the code is wrong.'),
             ('Import before rewrite',
              'Rebuilding an estate from scratch to "do it properly" is how migrations die. '
              'Import what exists, get it green, then improve it under version control.'),
             ('Leave a library, not a black box',
              'The deliverable is modules and documentation your engineers own. If your team '
              'cannot extend it after I leave, it was not finished.')],
        proof=[('Knab', 'Migrated legacy infrastructure to an IaC model with Terraform and '
                'PowerShell, making environments consistent and reproducible across a regulated '
                'estate.'),
               ('LeasePlan', 'Replaced manual OpenText instance setup with Terraform and Ansible '
                'Tower, removing a large slice of repetitive configuration work.'),
               ('Patchman', 'Orchestrated an entire Linode VM estate with Puppet, keeping every '
                'node consistent — the same discipline, a different tool.')],
        fit=['Your infrastructure exists only in the console and in one person\'s memory.',
             'You have Terraform but it has become a tangle nobody wants to run plan against.',
             'Environments drift, and nobody is quite sure how staging differs from production.',
             'You want IaC set up properly once, by someone who has untangled it before.'],
        related=['aws-cloud-consultant', 'cicd-devops-engineer', 'cloud-security-hardening'],
    ),
    dict(
        slug='cicd-devops-engineer',
        title='Freelance CI/CD Engineer — Pipelines That Ship Safely',
        desc='Freelance CI/CD and developer experience engineer, Utrecht. Azure DevOps, GitHub Actions and Jenkins pipelines, plus release and dependency automation.',
        h1='Freelance CI/CD and developer experience engineer',
        service_name='CI/CD and developer experience',
        lede=('I spent a stretch on a bank\'s Developer Experience team, which is a good way to '
              'learn that most pipeline problems are really organisational problems wearing a '
              'YAML costume.'),
        takes_on=[
            ('Pipeline design and repair', 'Azure DevOps, GitHub Actions and Jenkins. Builds that '
             'are fast enough that people stop working around them, and releases that are dull '
             'enough to do on a Friday.'),
            ('Release and change automation', 'Automated releases with change tickets generated '
             'as a side effect, so change management stops being a manual tax on every deploy.'),
            ('Dependency and compliance toil', 'RenovateBot for dependency updates and OpsLevel '
             'for service ownership and compliance reporting — the work that otherwise turns into '
             'a nagging Slack channel.'),
            ('Self-hosted runners', 'When hosted CI gets expensive or too restrictive, moving to '
             'self-hosted runners under configuration management, with the cost and control that '
             'brings back.'),
        ],
        how=[('Measure the thing people complain about',
              'Usually the complaint is "CI is slow", and usually the real cost is somewhere '
              'nobody has timed. Find it before rewriting anything.'),
             ('Automate the boring gate, not the judgement',
              'Scanning, dependency bumps, ticket creation and compliance evidence should be '
              'automatic. Whether to ship on a given day should stay a human decision.'),
             ('Reduce the number of things to remember',
              'The measure of developer experience is how much a developer has to hold in their '
              'head to release safely. Lower is better, and it is a real deliverable.')],
        proof=[('Knab — Developer Experience', 'Automated compliance reporting and dependency '
                'updates with OpsLevel and RenovateBot, cutting technical debt and the cognitive '
                'load carried by product teams.'),
               ('Knab — pipelines', 'Owned and optimised the Azure DevOps pipeline estate, and '
                'designed an automated release mechanism with auto-generated change tickets for a '
                'regulated environment.'),
               ('3D Hubs', 'Moved CI/CD off a hosted service onto self-hosted Jenkins managed by '
                'Puppet, lowering build costs, and wrote a custom GitHub Action bot in TypeScript '
                'that automated the deployment workflow end to end.')],
        fit=['Releases are a ceremony, and everyone dreads them.',
             'Your build times have quietly doubled and nobody owns the pipeline.',
             'Dependency updates and compliance evidence are done by hand, or not at all.',
             'You want a platform or DevEx function set up without hiring a whole team for it.'],
        related=['terraform-consultant', 'cloud-security-hardening', 'observability-monitoring'],
    ),
    dict(
        slug='cloud-security-hardening',
        title='Cloud Security & Compliance Hardening — AWS, Containers',
        desc='Freelance cloud security engineer, Utrecht. AWS WAF, CloudFront and Shield, distroless containers, and Trivy and OWASP ZAP scanning in the pipeline.',
        h1='Cloud security and compliance hardening',
        service_name='Cloud security and compliance hardening',
        lede=('Security has been the lens I look at infrastructure through since building a '
              'Slackware-based security distribution with friends in the early 2000s. It is not '
              'a phase at the end of a project.'),
        takes_on=[
            ('The edge', 'AWS WAF, CloudFront and Shield in front of public-facing load '
             'balancers — closing off the part of the estate the internet can actually reach.'),
            ('Containers', 'Migrating production workloads to distroless images, so a compromised '
             'container has no shell, no package manager and very little to work with.'),
            ('Shift-left scanning', 'SonarCloud, Trivy and OWASP ZAP wired into the build, so '
             'findings arrive while the code is still fresh rather than in a quarterly report.'),
            ('Evidence for auditors', 'Automated compliance reporting and ownership data, so an '
             'audit becomes a document you generate instead of a project you staff.'),
            ('Network security', 'Segmentation, VPN estates on pfSense, WireGuard or OpenVPN, and '
             'the Cisco background to go with it — CCNA and Cisco Security Green Belt.'),
        ],
        how=[('Fix the reachable surface first',
              'Effort goes where an attacker can actually get. The public edge and the container '
              'runtime before the theoretical risks further down the list.'),
             ('Make the secure path the easy path',
              'Controls developers have to remember get skipped under deadline. Controls built '
              'into the pipeline and the base image do not.'),
             ('Produce evidence as a by-product',
              'In regulated environments the control is only half the work — proving it ran is '
              'the other half. Both should be automatic.')],
        proof=[('Knab', 'Moved 34 production services to distroless images, cutting reported '
                'vulnerabilities from thousands to under 20, and put AWS WAF, CloudFront and '
                'Shield in front of the 3 customer identity endpoints — inside a Dutch bank.'),
               ('Knab — pipelines', 'Integrated SonarCloud, Trivy and OWASP ZAP scanning into '
                'Azure DevOps builds to shift security left, and automated the change-management '
                'trail around releases.'),
               ('Cisco, via 3Pillar Global', 'Python automation for Cisco FirePower next-generation '
                'firewalls — security tooling from the inside.')],
        fit=['You are regulated, and an audit is coming.',
             'Your public endpoints have no WAF in front of them and you know it.',
             'Container images are inherited, enormous, and full of things you do not ship.',
             'Security findings arrive as a PDF once a quarter instead of in the pipeline.'],
        related=['aws-cloud-consultant', 'cicd-devops-engineer', 'network-engineering'],
    ),
    dict(
        slug='observability-monitoring',
        title='Observability Consultant — Datadog, New Relic, Grafana',
        desc='Freelance observability consultant, Utrecht. Datadog, New Relic, Prometheus, Grafana and Splunk — alerting that reflects real failure, not noise.',
        h1='Observability that earns its keep',
        service_name='Observability and monitoring',
        lede=('Every team I have joined had monitoring. Fewer had alerting anyone trusted. The '
              'gap between those two things is where incidents live.'),
        takes_on=[
            ('Instrumentation', 'Datadog, New Relic, Prometheus and Grafana, plus Splunk and ELK '
             'on the logging side. Getting the signals out of the system in the first place.'),
            ('Custom checks', 'The checks that matter are usually specific to your application, '
             'not the ones that ship in the box. Writing those is most of the value.'),
            ('Alert hygiene', 'Cutting the alerts nobody acts on. An on-call rotation that has '
             'learned to ignore its pager is worse than no pager.'),
            ('Dashboards people actually open', 'Fewer panels, chosen to answer the questions '
             'asked at three in the morning.'),
        ],
        how=[('Start from the incidents you have had',
              'Your last six incidents tell you what to instrument far better than a vendor '
              'checklist does.'),
             ('Alert on symptoms, not causes',
              'Page when users are affected or about to be. Everything else is a dashboard or a '
              'ticket, not a phone call at 03:00.'),
             ('Every alert needs an action',
              'If there is nothing to do about it, it is not an alert. That one rule removes most '
              'of the noise in a typical estate.')],
        proof=[('LeasePlan', 'Designed a Datadog alerting layer with custom checks that surfaced '
                'performance bottlenecks proactively, on infrastructure where availability was '
                'contractual.'),
               ('3D Hubs', 'Prometheus and the ELK stack across rebuilt AWS environments.'),
               ('Knab', 'New Relic across a regulated banking platform, and Splunk in the earlier '
                'engagement.')],
        fit=['You find out about outages from customers.',
             'Your on-call rotation has quietly stopped reading the alerts.',
             'You are paying for an observability platform and using ten percent of it.',
             'Something is slow, intermittently, and nobody can prove where.'],
        related=['aws-cloud-consultant', 'cicd-devops-engineer', 'cloud-security-hardening'],
    ),
    dict(
        slug='network-engineering',
        title='Network Engineering — Hybrid Cloud, VPN & Segmentation',
        desc='Freelance network engineer, Utrecht. Hybrid cloud connectivity, segmentation, and VPN estates on pfSense, WireGuard and OpenVPN. CCNA certified.',
        h1='Network engineering and connectivity',
        service_name='Network engineering and connectivity',
        lede=('Before cloud I did telecom — 4G and LTE rollout, MPLS, and Alcatel-Lucent 7750 SR '
              'service routers. That background is why cloud networking problems tend not to '
              'surprise me.'),
        takes_on=[
            ('Hybrid connectivity', 'Joining an office, a data centre and a cloud estate together '
             'without creating one flat network where everything can reach everything.'),
            ('Segmentation', 'VPC and subnet design, security groups and routing that reflect an '
             'actual trust model rather than whatever was quickest at the time.'),
            ('VPN estates', 'pfSense, WireGuard and OpenVPN — site-to-site and remote access, '
             'built to be operated rather than admired.'),
            ('Load balancing and failover', 'HAProxy and Keepalived for services that cannot '
             'afford a single point of failure.'),
        ],
        how=[('Draw the real topology',
              'Almost every network engagement starts by discovering the diagram is out of date. '
              'That discovery is usually the most valuable week.'),
             ('Default deny, then open deliberately',
              'Segmentation is only worth anything if the default is closed. Retrofitting that is '
              'work, but it is finite work.'),
             ('Document it for the person on call',
              'A network nobody but you can reason about is a liability, however elegant it is.')],
        proof=[('Patchman', 'Scaled Redis, PostgreSQL and Nginx for high availability using '
                'Keepalived and HAProxy across a Linode estate.'),
               ('Alcatel-Lucent / Nokia', '4G and LTE rollout and network monitoring, then telecom '
                'KPI data work — MPLS and 7750 SR at carrier scale.'),
               ('Certification', 'CCNA (Routing & Switching), Cisco Security Green Belt, and '
                'Alcatel-Lucent Certified Field Expert in MPLS and 7750 SR.')],
        fit=['Your cloud network grew organically and is now effectively flat.',
             'You need a site-to-site or remote-access VPN estate someone can actually maintain.',
             'A hybrid setup needs joining up without opening everything to everything.',
             'You want a segmentation model designed once, by someone who did this before cloud.'],
        related=['cloud-security-hardening', 'aws-cloud-consultant', 'observability-monitoring'],
    ),
]

BY_SLUG = {p['slug']: p for p in PAGES}
E = html.escape


def nav_html():
    links = '\n'.join(f'      <a href="{h}">{E(t)}</a>' for h, t in NAV)
    return f'''    <nav class="site-nav" id="site-nav" aria-label="Primary">
{links}
      <a class="nav-cta" href="/#contact">Get in touch</a>
    </nav>'''


def render(p):
    url = f"{ORIGIN}/{p['slug']}/"

    takes = '\n'.join(
        f'''        <div class="takes-item">
          <h3>{E(t)}</h3>
          <p>{E(d)}</p>
        </div>''' for t, d in p['takes_on'])

    how = '\n'.join(
        f'''        <li>
          <span class="step-num">{i:02d}</span>
          <h3>{E(t)}</h3>
          <p>{E(d)}</p>
        </li>''' for i, (t, d) in enumerate(p['how'], 1))

    proof = '\n'.join(
        f'''        <li>
          <span class="proof-who">{E(w)}</span>
          <span class="proof-what">{E(d)}</span>
        </li>''' for w, d in p['proof'])

    fit = '\n'.join(f'          <li>{E(f)}</li>' for f in p['fit'])

    related = '\n'.join(
        f'''        <a class="related-card" href="/{r}/">
          <span class="related-label">{E(BY_SLUG[r]["service_name"])}</span>
          <span class="related-go">Read more</span>
        </a>''' for r in p['related'])

    ld = {
        "@context": "https://schema.org",
        "@graph": [
            {"@type": "Service", "@id": url + "#service", "name": p['service_name'],
             "description": p['desc'], "serviceType": p['service_name'],
             "provider": {"@id": f"{ORIGIN}/#business"},
             "areaServed": [{"@type": "Country", "name": "Netherlands"},
                            {"@type": "Place", "name": "European Union (remote)"}],
             "url": url},
            {"@type": "WebPage", "@id": url, "url": url, "name": p['title'],
             "description": p['desc'], "inLanguage": "en-GB",
             "isPartOf": {"@id": f"{ORIGIN}/#website"},
             "about": {"@id": url + "#service"},
             "breadcrumb": {"@id": url + "#breadcrumb"}},
            {"@type": "BreadcrumbList", "@id": url + "#breadcrumb", "itemListElement": [
                {"@type": "ListItem", "position": 1, "name": "Codeverse", "item": ORIGIN + "/"},
                {"@type": "ListItem", "position": 2, "name": "Services", "item": ORIGIN + "/#services"},
                {"@type": "ListItem", "position": 3, "name": p['service_name']},
            ]},
        ],
    }

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{p['title']}</title>
<meta name="description" content="{E(p['desc'])}">
<link rel="canonical" href="{url}">
<meta name="robots" content="index, follow, max-image-preview:large, max-snippet:-1">
<meta name="author" content="Mihai Cindea">

<meta name="geo.region" content="NL-UT">
<meta name="geo.placename" content="Utrecht, Netherlands">

<meta property="og:type" content="article">
<meta property="og:site_name" content="Codeverse">
<meta property="og:title" content="{E(p['h1'])} — Codeverse">
<meta property="og:description" content="{E(p['desc'])}">
<meta property="og:url" content="{url}">
<meta property="og:locale" content="en_GB">
<meta property="og:image" content="{ORIGIN}/assets/img/og.png">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{E(p['h1'])} — Codeverse">
<meta name="twitter:description" content="{E(p['desc'])}">
<meta name="twitter:image" content="{ORIGIN}/assets/img/og.png">

<link rel="icon" href="/favicon.svg" type="image/svg+xml">
<link rel="alternate icon" href="/favicon.ico">
<link rel="stylesheet" href="/assets/css/style.css">
</head>
<body>

<a class="skip-link" href="#main">Skip to content</a>

<header class="site-header">
  <div class="wrap header-inner">
    <a class="brand" href="/" aria-label="Codeverse home">
      <svg class="brand-mark" width="28" height="28" viewBox="0 0 32 32" aria-hidden="true" focusable="false">
        <path d="M16 2.6 28 9.3v13.4L16 29.4 4 22.7V9.3z" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round"/>
        <path d="M20.6 12.2a5.8 5.8 0 1 0 0 7.6" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round"/>
      </svg>
      <span class="brand-text">Codeverse</span>
    </a>

    <button class="nav-toggle" id="nav-toggle" aria-expanded="false" aria-controls="site-nav" aria-label="Open menu">
      <span></span><span></span><span></span>
    </button>

{nav_html()}
  </div>
</header>

<main id="main">

  <section class="section page-head">
    <div class="wrap">
      <nav class="crumbs" aria-label="Breadcrumb">
        <a href="/">Codeverse</a> <span aria-hidden="true">/</span>
        <a href="/#services">Services</a> <span aria-hidden="true">/</span>
        <span aria-current="page">{E(p['service_name'])}</span>
      </nav>
      <h1>{E(p['h1'])}</h1>
      <p class="lede">{E(p['lede'])}</p>
      <div class="hero-actions">
        <a class="btn btn-primary" href="/#contact">Start a conversation</a>
        <a class="btn btn-ghost" href="/#work">See the track record</a>
      </div>
    </div>
  </section>

  <section class="section section-alt">
    <div class="wrap">
      <p class="eyebrow">Scope</p>
      <h2 class="section-title">What I take on</h2>
      <div class="takes-grid">
{takes}
      </div>
    </div>
  </section>

  <section class="section">
    <div class="wrap">
      <p class="eyebrow">Method</p>
      <h2 class="section-title">How it runs</h2>
      <ol class="steps">
{how}
      </ol>
    </div>
  </section>

  <section class="section section-alt">
    <div class="wrap">
      <p class="eyebrow">Evidence</p>
      <h2 class="section-title">Where this has been done before</h2>
      <ul class="proof-list">
{proof}
      </ul>
    </div>
  </section>

  <section class="section">
    <div class="wrap fit-inner">
      <div>
        <p class="eyebrow">Fit</p>
        <h2 class="section-title">Probably worth a conversation if</h2>
        <ul class="fit-list">
{fit}
        </ul>
      </div>
      <aside class="related">
        <h3>Related services</h3>
{related}
      </aside>
    </div>
  </section>

  <section class="section section-contact">
    <div class="wrap">
      <div class="contact-card">
        <p class="eyebrow">Contact</p>
        <h2 class="section-title">Tell me what is actually broken</h2>
        <p class="section-lede">
          The contact details live on the front page. If I am not the right person for this,
          I will say so.
        </p>
        <div class="contact-actions">
          <a class="btn btn-primary" href="/#contact">Get in touch</a>
          <a class="btn btn-ghost" href="/">Back to the front page</a>
        </div>
      </div>
    </div>
  </section>

</main>

<footer class="site-footer">
  <div class="wrap footer-inner">
    <p class="footer-brand">
      <span class="brand-text">Codeverse</span>
      <span class="footer-tag">Cloud &amp; DevOps engineering · Utrecht, NL</span>
    </p>
    <p class="footer-links">
      Open source: <a href="https://dvrbridge.codeverse.nl/">dvrbridge — RTSP for old CCTV DVRs</a>
      · <a href="https://github.com/kiwimato" rel="me noopener">GitHub</a>
    </p>
    <p class="footer-copy">&copy; <span id="year">2026</span> Codeverse — Mihai Cindea. All rights reserved.</p>
  </div>
</footer>

<script type="application/ld+json">
{json.dumps(ld, ensure_ascii=False, indent=2)}
</script>

<script src="/assets/js/main.js" defer></script>
</body>
</html>
'''


def main():
    written = []
    for p in PAGES:
        d = os.path.join(SITE, p['slug'])
        os.makedirs(d, exist_ok=True)
        path = os.path.join(d, 'index.html')
        with open(path, 'w', encoding='utf-8') as f:
            f.write(render(p))
        written.append(f"/{p['slug']}/")
    print('generated:', ', '.join(written))


if __name__ == '__main__':
    main()
