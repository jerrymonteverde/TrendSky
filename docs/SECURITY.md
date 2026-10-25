# Security — foundation

Secrets are environment-based and `.env` is ignored. Existing local secrets are never rewritten by setup. Compose requires separate admin/application passwords and does not publish PostgreSQL. Database bootstrap creates a non-superuser application role; it has DDL permission for the initial shared migration setup. A separate migration owner/read-only API role is a production hardening follow-up when write paths arrive.

Web/API containers run as non-root users. Caddy is the HTTPS ingress; development ports bind to loopback. API SQL uses SQLAlchemy bound expressions. Public methods are read-only. There are no administrative API operations. CORS lists explicit origins, and API error responses omit connection details. Next.js responses set frame, MIME, referrer and capability headers.

The per-process request limiter has a bounded 10,000-client map and fixed one-minute windows. It does not trust forwarding headers. Behind a proxy, clients share that proxy's budget. This is conservative but not suitable as a per-user distributed limiter; introduce an ingress/distributed limiter before multi-worker scale. Liveness/readiness are exempt for reliable probes. The web request timeout prevents a slow data service from indefinitely blocking pages.

No public posts or private data are collected in Milestone 1. Retention/deletion procedures for source content must be implemented before ingestion starts; no compliance certification is claimed. Logs should never include credentials, raw payloads or query strings. CI runs npm and Python runtime vulnerability audits. Dependency audits are point-in-time checks, not guarantees.

Before public deployment: verify container startup and database migrations, restrict SSH/firewall access, set DNS/TLS, verify backups and restoration, review exposed API docs/health metadata and configure operational alerts. No public deployment has been performed by this milestone.
