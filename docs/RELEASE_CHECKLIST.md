# GitHub release checklist

Before publishing a release:

- [ ] Run `python -m unittest discover -s tests -v`.
- [ ] Rebuild the Compose stack from clean disposable volumes and run production, security, load, backup-restore, and recovery checks.
- [ ] Confirm duplicate review is review-only, owner/editor/viewer denial works, and audit/provenance screens show expected data.
- [ ] Confirm Cloudflare Tunnel, HTTPS, Cloudflare Access OTP, application sign-in, import/search/export, background jobs, and optional alert delivery.
- [ ] Rotate any secret ever displayed in a terminal, screenshot, chat, or browser developer tools; recreate the local `.env` without committing it.
- [ ] Confirm no `.env`, API keys, customer CSVs, databases, or personal data are staged.
- [ ] Review `LICENSE` and `THIRD_PARTY_NOTICES.md` for new dependencies or assets.
- [ ] Confirm every enabled data source permits the collection, retention, and use you describe.
- [ ] Keep the product description accurate: local CSV import and local search are implemented; global discovery is not yet included.
- [ ] Review the public name, domains, and trademark registers in launch markets.
- [ ] Update the README if behavior or data rights change.
- [ ] Review `assets/ASSET_PROVENANCE.md` for every added or changed visual.
- [ ] Verify all public documentation uses fictional examples and makes only
  factual, bounded claims.
