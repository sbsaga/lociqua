# What problem does Lociqua solve?

Many teams have company data in spreadsheets, CRM exports, or internal files.
Those lists are hard to search, contain duplicate records, and lose track of
where each record came from. Lociqua turns authorized business data into a local
directory that is easier to use.

## Example

An agency imports a CSV of businesses. A user searches for `software` in Baner,
Hinjewadi, and Kharadi. Lociqua starts the three searches independently and
shows one tab for each locality. Each tab can show up to five matching records.

## What Lociqua does today

- Imports UTF-8 CSV files containing a `name` column.
- Stores records locally in SQLite.
- Normalizes names, domains, website URLs, phones, and categories.
- Preserves the import source for each record.
- Searches one or more locations concurrently.
- Keeps results separated by location in the dashboard.

## What it does not do

Lociqua does not scrape Google Maps, bypass restrictions, or guarantee a global
business directory. It only finds records that have been legally imported or
provided by a configured authorized provider.
