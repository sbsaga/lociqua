# Third-party notices

Lociqua's Python production dependencies include:

| Dependency | Purpose | Upstream license reference |
| --- | --- | --- |
| `psycopg` / `psycopg-binary` | PostgreSQL connection adapter | [LGPL-3.0-only](https://www.psycopg.org/download/) |
| `redis` (redis-py) | Redis client | [MIT](https://github.com/redis/redis-py/blob/master/LICENSE) |

The production Compose profile also obtains container images for Python,
PostgreSQL/PostGIS, Redis, and Nginx. Operators must review the exact image
versions, their licenses, notices, security advisories, and deployment terms
before distribution or commercial use.

This inventory is maintained as a practical notice, not legal advice. Add every
new dependency, provider SDK, dataset, font, image, or copied code fragment to
this file and review its license obligations before release.
