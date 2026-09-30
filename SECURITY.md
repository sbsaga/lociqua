# Security policy

Do not report security vulnerabilities in public issues. Send a private report to
the repository maintainer with reproduction steps, affected version, impact, and
a safe proof of concept. Do not include real credentials or personal data.

For deployment, put the service behind TLS and authentication, keep it bound to
a trusted network, protect backups, enforce request limits, and use secret
management. The reference HTTP server is a local development server, not an
internet-facing production deployment.
