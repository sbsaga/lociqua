# Authorised web research

Lociqua's web-research capability is for saving evidence that a person has
reviewed from a source their organisation is permitted to use. It is not an
internet scraper, Google/Maps collector, CAPTCHA solver, proxy tool, or browser
automation product.

## Safe workflow

1. An owner records a source policy: domain, permission basis, allowed fields,
   retention, export rule, attribution, and status.
2. The owner approves a `browser_capture` policy only after checking the source
   contract, licence, privacy obligations, and any attribution requirement.
3. An editor opens the source normally in Chrome or Edge and clicks the Lociqua
   extension. The extension reads only the current URL, title, and optional text
   selection after that explicit interaction.
4. The editor selects and confirms the exact fields to save. Lociqua records
   the URL, capture time, user, policy, content fingerprint, and review state.
5. An editor or owner reviews evidence. Evidence supports a record but never
   silently replaces it; duplicate review remains non-destructive.

## Source-policy defaults

Browser capture is denied unless a matching `browser_capture` policy is
`approved`. A policy can cover its own domain and subdomains, but never a
sibling or lookalike domain. Policies may prohibit export, require attribution,
limit fields, and set a retention period. The worker removes expired evidence
and writes an audit event; it does not delete the company record itself.

## Extension installation

Use the instructions in [the extension README](../extension/README.md). The
extension keeps its configured URL and short-lived access token in browser
session storage. Closing the browser clears that session. Do not enter a
long-lived owner credential into the extension.

## Operator responsibility

The software records permission claims; it cannot determine whether a source
licence, privacy law, contract, or employment policy permits a capture. Review
those requirements before approving a source. The repository licence applies to
Lociqua code and assets, not third-party data rights.
