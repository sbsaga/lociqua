# The enterprise problem Lociqua targets

Organizations commonly hold the same business entity in several forms: a CRM
account, a supplier file, a branch-office spreadsheet, and a directory export.
The records often disagree or omit critical information. Users need to know
which record to use, where a field came from, whether the source permits its
use, and what changed over time.

Lociqua is scoped to business entities rather than trying to replace a general
enterprise data-governance platform. Its trust model is:

```text
Authorized source → validated import → canonical company → provenance + quality → search/export
```

The product must never imply that a high quality score proves a company’s facts
are true. It is a transparent measure of available fields and basic formatting.
Human review and source-specific verification remain essential.
