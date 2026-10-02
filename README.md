# Lociqua

> Turn business data you are allowed to use into a searchable, reviewable local directory.

![Illustration of separate business records from several locations becoming one organized directory](assets/lociqua-readme-hero.png)

## Start here: what is this for?

Imagine that your team has business information in several CSV files: a customer
export, a partner list, and an approved local directory. Someone asks, “Which
companies match this need in Pune, Mumbai, and Bengaluru?” Today, that often
means opening many files, repeating the same search, and wondering which row is
current or where it came from.

Lociqua gives that permitted data one organized home. You import the files you
are allowed to use; Lociqua makes the records easier to search, keeps their
source history, points out possible duplicates for a person to review, and lets
authorized people export results. It is designed for your organisation's data,
not for collecting the whole internet.

![Illustration of messy business files becoming clean, checked business records](assets/lociqua-from-files-to-records.png)

**In one sentence:** Lociqua helps a team find and maintain trusted business
records without losing track of their origin.

New here? Read [First steps: from file to result](docs/FIRST_STEPS.md).

## What Lociqua does

- Imports bounded UTF-8 CSV data and records source metadata.
- Normalizes common company fields and supports multi-location search.
- Preserves source records, field provenance, quality indicators, and audit
  history.
- Presents explainable duplicate candidates for human review; decisions do not
  merge or delete either company.
- Provides viewer, editor, and owner roles in the PostgreSQL/Redis production
  profile.
- Supports self-hosting with Docker Compose, health checks, metrics, structured
  logs, backup/restore helpers, and an optional generic alert webhook.
- Supports owner-approved, user-assisted web evidence capture with provenance,
  review, retention, and export controls; it does not automate browsing.

![Illustration of an owner allowing approved sources through a policy gate while rejecting unapproved sources](assets/lociqua-approved-source-governance.png)

![Illustration of authorized files moving through a protected directory into searchable records](assets/lociqua-trusted-data-flow.png)

## What Lociqua does not do

- It does not scrape restricted sources, bypass access controls, solve CAPTCHAs,
  rotate proxies, or automate browser collection.
- It does not claim a global business directory, verified company truth, or
  automatic legal compliance.
- It does not destructively merge records based on duplicate suggestions.
- It is a self-hosted, single-configured-workspace application, not a hosted
  multi-tenant SaaS product.

This boundary matters: importing a file does not make its use legal. The person
or organisation operating Lociqua must check the source licence, privacy rules,
contracts, and any required attribution.

## Web research without an uncontrolled scraper

Lociqua can help when a researcher is already viewing a permitted website. An
owner first approves that source and records the applicable conditions. Then an
editor can use the optional browser extension to choose a few fields, inspect a
preview, and deliberately save them as evidence. The original URL, policy,
capture time, and reviewer decision stay connected to the record.

![Illustration of a person selecting, reviewing, and confirming only chosen business fields before saving them as protected evidence](assets/lociqua-human-evidence-capture.png)

This is deliberately different from a scraper: Lociqua does not visit websites
by itself, harvest search-result pages, or work around restrictions.

## What a normal day with Lociqua looks like

| Step | What you do | What Lociqua helps with |
| --- | --- | --- |
| 1. Bring permitted data | Import an approved CSV file. | Checks its shape, records the source, and reports accepted or rejected rows. |
| 2. Find companies | Search a category or name across one or more places. | Keeps location tasks bounded and groups the returned records clearly. |
| 3. Check the result | Open a company record. | Shows quality signals, missing fields, source provenance, and history. |
| 4. Review uncertainty | Inspect a possible duplicate. | Explains why it looks similar; approval or rejection never deletes either record. |
| 5. Share carefully | Export only when authorised. | Requires sign-in and applies your role permissions. |

![Illustration of one person searching several locations and receiving separate grouped results](assets/lociqua-multi-location-search.png)

![Illustration of a human reviewing two similar records while their source history stays preserved](assets/lociqua-duplicate-review.png)

## Choose your path

| Goal | Start here |
| --- | --- |
| I want to understand the problem | [What problem Lociqua solves](docs/WHAT_PROBLEM.md) and [use cases](docs/USE_CASES.md) |
| I have no technical background | [First steps: from file to result](docs/FIRST_STEPS.md) |
| I want to use the application | [User guide](docs/USER_GUIDE.md) |
| I want to self-host it | [Self-hosting guide](docs/SELF_HOSTING.md) and [operations runbook](docs/OPERATIONS.md) |
| I need data-rights guidance | [Security and data rights](docs/SECURITY_AND_DATA_RIGHTS.md) |
| I want permitted browser-assisted research | [Authorised web research](docs/AUTHORIZED_WEB_RESEARCH.md) |
| I need a simple operating workflow | [Web research playbook](docs/WEB_RESEARCH_PLAYBOOK.md) |
| I want to build or contribute | [Architecture](docs/ARCHITECTURE.md), [API reference](docs/API.md), and [contributing guide](CONTRIBUTING.md) |

## Quick start

Python 3.11+ is required. The production profile uses PostgreSQL/PostGIS and
Redis; local development can use SQLite.

```powershell
python -m pip install -e .
python -m unittest discover -s tests -v
```

For a production-style local stack, copy `.env.example` to a private `.env`,
replace every example secret, and run:

```powershell
docker compose -f docker-compose.production.yml up --build -d --remove-orphans
Invoke-WebRequest http://127.0.0.1/healthz
```

Open `http://127.0.0.1/` and sign in with the local bootstrap account. See the
[self-hosting guide](docs/SELF_HOSTING.md) before exposing the service publicly.

## Data rights and safety

Only import data you own, receive with permission, or use under a license that
permits the intended collection, retention, search, export, and redistribution.
The Apache-2.0 license covers repository code and contributed assets; it does
not grant rights to third-party data, brands, personal information, or contracts.
Read [security and data rights](docs/SECURITY_AND_DATA_RIGHTS.md) before a real
deployment.

## Documentation

The complete documentation index is at [docs/README.md](docs/README.md). It
includes user workflows, deployment, operations, production testing, release
checks, architecture, API details, and original-asset provenance.

![Illustration of quality review that keeps source information connected to a company record](assets/lociqua-quality-and-provenance.png)

![Illustration of a protected, self-hosted Lociqua deployment under the operator's control](assets/lociqua-self-hosted-control.png)

![Illustration of evidence progressing through human review, audit history, and retention](assets/lociqua-evidence-lifecycle.png)

## Status and release discipline

The repository includes a production-oriented Compose profile, but a truthful
production-readiness claim still requires verification in the target environment:
authenticated load testing, backup/restore drills, recovery tests, HTTPS and
identity-boundary checks, alert delivery, and secret rotation. See
[production testing](docs/PRODUCTION_TESTING.md) and the
[release checklist](docs/RELEASE_CHECKLIST.md).
