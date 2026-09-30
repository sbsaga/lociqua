# First steps: from a file to an answer

This page is for someone who has never used a business-data system before.
Lociqua is not a search engine that discovers every company online. It is a
private tool for arranging business data that your organisation is permitted to
use.

![Illustration of separate business files becoming clean business records](../assets/lociqua-from-files-to-records.png)

## The problem in plain language

Suppose three colleagues each keep a list of local businesses. One list has
phone numbers, another has websites, and a third has an old address. Finding
“all software companies in these three cities” can take a long time. The same
company might be present several times, and nobody may know which file supplied
each value.

Lociqua makes this work easier to manage. It does not decide that data is true;
it gives people a clear place to search it, check it, and keep its history.

## Before you begin

You need:

- A CSV file your organisation owns or has permission to use.
- At least a `name` column. Adding `city`, `country`, `website`, `phone`, or
  `categories` makes later search more useful.
- A Lociqua account from your workspace owner.
- Permission to export or share the results if you plan to do so.

Do not import a file simply because it is visible online. Rights to collect,
store, search, contact, export, or redistribute data can be different.

## Your first five actions

1. **Sign in.** Open the Lociqua address given by your administrator and sign
   in. If the organisation uses an additional access screen, complete that first.
2. **Import a permitted CSV.** Select **Import**, choose the file, and submit it.
   Read the accepted/rejected report. Fix rejected rows in the original file.
3. **Search.** Enter a company name, category, or other supported keyword, then
   add the locations you care about. Lociqua processes the locations as separate
   bounded tasks so results are not silently mixed.
4. **Open a record.** Check whether the contact details look complete, then look
   at source and history information before relying on it.
5. **Review or export.** Editors and owners can review duplicate candidates.
   Export only when your role and the source rules allow it.

![Illustration of separate location searches arriving as separate result groups](../assets/lociqua-multi-location-search.png)

## If two records look like the same company

Lociqua can flag a possible duplicate. That is a prompt for a human, not an
automatic deletion. An editor or owner can approve or reject the suggested
match, and both original records remain in the directory.

![Illustration of a reviewer comparing two similar records while source history remains visible](../assets/lociqua-duplicate-review.png)

## Which guide should you read next?

| Your situation | Next guide |
| --- | --- |
| I want the exact button-by-button workflow | [User guide](USER_GUIDE.md) |
| I need examples of who uses this | [Use cases](USE_CASES.md) |
| I need to install it for my organisation | [Self-hosting](SELF_HOSTING.md) |
| I must check data rights or privacy | [Security and data rights](SECURITY_AND_DATA_RIGHTS.md) |

Return to the [documentation index](README.md) or the [project README](../README.md).
