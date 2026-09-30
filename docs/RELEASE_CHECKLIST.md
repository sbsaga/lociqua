# GitHub release checklist

Before publishing a release:

- [ ] Run `python -m unittest discover -s tests -v`.
- [ ] Confirm no `.env`, API keys, customer CSVs, databases, or personal data are staged.
- [ ] Review `LICENSE` and `THIRD_PARTY_NOTICES.md` for new dependencies or assets.
- [ ] Confirm every enabled data source permits the collection, retention, and use you describe.
- [ ] Keep the product description accurate: local CSV import and local search are implemented; global discovery is not yet included.
- [ ] Review the public name, domains, and trademark registers in launch markets.
- [ ] Update the README if behavior or data rights change.
