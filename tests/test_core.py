import asyncio
import tempfile
import unittest

from business_discovery.models import Company, SearchQuery, SearchRequest
from business_discovery.normalization import deduplicate
from business_discovery.orchestrator import SearchOrchestrator
from business_discovery.providers import FixtureProvider
from business_discovery.providers import LocalDatabaseProvider
from business_discovery.storage import CompanyStore
from business_discovery.importers import import_csv
from business_discovery.importers import preview_csv


class CoreTests(unittest.TestCase):
    def test_validation(self):
        with self.assertRaises(ValueError):
            SearchQuery("", "Pune").validate(100)

    def test_domain_deduplication(self):
        values = deduplicate([Company("1", " A ", website="example.com"), Company("2", "B", website="https://www.example.com/x")])
        self.assertEqual(len(values), 1)

    def test_identical_tasks_coalesce(self):
        async def run():
            service = SearchOrchestrator([FixtureProvider()])
            query = SearchQuery("dentists", "Kothrud")
            return await service.search(SearchRequest((query, query)))
        result = asyncio.run(run())
        self.assertEqual(result["results_count"], 1)
        self.assertEqual(result["completed_tasks"], 2)

    def test_import_and_search_owned_csv(self):
        with tempfile.TemporaryDirectory() as directory:
            store = CompanyStore(f"{directory}/companies.db")
            report = import_csv(b"name,categories,locality,city\nAcme AI,AI software,Baner,Pune\n", store)
            self.assertEqual(report.accepted, 1)
            async def run():
                service = SearchOrchestrator([LocalDatabaseProvider(store)])
                return await service.search(SearchRequest((SearchQuery("AI", "Baner", provider_preference=("local_database",)),)))
            self.assertEqual(asyncio.run(run())["results_count"], 1)

    def test_preview_does_not_require_import(self):
        preview = preview_csv(b"name,city\nAcme,Pune\n")
        self.assertTrue(preview.valid)
        self.assertEqual(preview.sample_rows[0]["name"], "Acme")

    def test_saved_search(self):
        with tempfile.TemporaryDirectory() as directory:
            store = CompanyStore(f"{directory}/companies.db")
            store.save_search("Pune AI", "AI", "Pune", 5)
            self.assertEqual(store.saved_searches()[0]["name"], "Pune AI")

if __name__ == "__main__":
    unittest.main()
