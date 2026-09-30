# Getting started

Use this guide for a local development workflow. For the Docker production
profile, use [self-hosting](SELF_HOSTING.md).

## 1. Install

```powershell
python -m pip install -e .
python -m unittest discover -s tests -v
```

## 2. Start the local application

```powershell
python -c "from business_discovery.api import serve; serve()"
```

Open `http://127.0.0.1:8000/`. Local development can use SQLite; use the
PostgreSQL/Redis Compose profile for an operational deployment.

## 3. Import fictional example data

The repository's `examples/companies.csv` is fictional demonstration data. A
real CSV must be UTF-8 and include `name`. Useful optional fields include
`categories`, `website`, `phone`, `address`, `locality`, `city`, and `country`.

Only import information you are allowed to store and use.

## 4. Search locations

Enter a keyword and one location per line, for example:

```text
Keyword: software
Locations:
Baner
Hinjewadi
Kharadi
```

Each location is processed independently. Select a result to inspect quality,
source records, provenance, and audit history.

Next: [user guide](USER_GUIDE.md) or [self-hosting](SELF_HOSTING.md).
