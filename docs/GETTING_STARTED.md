# Getting started

You need Python 3.11 or newer. No API key or third-party account is required for
the local CSV workflow.

## 1. Install and run

```powershell
python -m pip install -e .
python -c "from business_discovery.api import serve; serve()"
```

Open `http://127.0.0.1:8000/` in your browser.

## 2. Import data

Use `examples/companies.csv` as a safe example. A CSV must be UTF-8 and include
a `name` column. Useful optional columns are `categories`, `website`, `phone`,
`address`, `locality`, `city`, and `country`.

## 3. Search multiple places

Enter a keyword and one location per line. For example:

```text
Keyword: AI
Locations:
Baner
Hinjewadi
Kharadi
```

Choose 5 results per location and select **Search all locations**. Every locality
gets its own tab and searches run concurrently.

## Command line alternative

```powershell
python -m business_discovery.cli import-csv examples/companies.csv
python -m business_discovery.cli search --keyword AI --location Baner
```
