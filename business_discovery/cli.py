from __future__ import annotations

import argparse
import asyncio
import json

from .models import SearchQuery, SearchRequest
from .orchestrator import SearchOrchestrator
from .providers import LocalDatabaseProvider
from .storage import CompanyStore


def main() -> None:
    parser = argparse.ArgumentParser(description="Terms-compliant business discovery")
    subcommands = parser.add_subparsers(dest="command", required=True)
    search = subcommands.add_parser("search")
    upload = subcommands.add_parser("import-csv")
    upload.add_argument("file")
    for target in (search,):
        target.add_argument("--keyword", required=True)
        target.add_argument("--location", required=True)
        target.add_argument("--max-results", type=int, default=25)
        target.add_argument("--provider", default="local_database", help="configured authorized provider name")
    args = parser.parse_args()
    store = CompanyStore()
    if args.command == "import-csv":
        from .importers import import_csv
        print(json.dumps(import_csv(open(args.file, "rb").read(), store).__dict__, indent=2)); return
    request = SearchRequest(queries=(SearchQuery(args.keyword, args.location, max_results=args.max_results,
                                                   provider_preference=(args.provider,)),))
    service = SearchOrchestrator([LocalDatabaseProvider(store)])
    print(json.dumps(asyncio.run(service.search(request)), indent=2))


if __name__ == "__main__":
    main()
