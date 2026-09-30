# Security and data rights

Lociqua is designed for data that an operator owns, receives with permission, or
uses under a license compatible with the intended collection, retention, search,
export, and redistribution. This is practical product guidance, not legal
advice.

## Source responsibilities

- Register each source and record its permission basis and license note.
- Retain required attribution, notices, and retention limits.
- Confirm that customer, employee, and personal data has an appropriate legal
  basis and access policy.
- Review provider contracts before configuring a provider adapter or export.
- Obtain qualified legal and privacy review for commercial, regulated, or
  cross-border use.

## Product boundaries

Lociqua does not include browser automation, access-control bypasses, CAPTCHA
solving, prohibited-source scraping, proxy rotation, or an unrestricted global
business directory. Its Apache-2.0 software license does not grant rights to
third-party data, trademarks, names, contact information, or source contracts.

## Operational security

- Keep `.env`, database volumes, CSV imports, backups, alert webhooks, and
  tunnel credentials private.
- Use the production PostgreSQL/Redis stack rather than a local development
  store for operational data.
- Put public traffic behind HTTPS and an identity boundary; limit access with
  Cloudflare Access or an equivalent operator-managed control.
- Use viewer, editor, and owner roles according to least privilege.
- Rotate exposed credentials, preserve relevant audit events during an incident,
  and test backups in an isolated restore database.

## Visual and content policy

Repository-authored diagrams are documented in [asset provenance](../assets/ASSET_PROVENANCE.md).
Before publishing new content or images, verify ownership, licensing, privacy,
and trademark implications. Do not imply endorsement by a provider or platform.

Next: [operations runbook](OPERATIONS.md) and [release checklist](RELEASE_CHECKLIST.md).
