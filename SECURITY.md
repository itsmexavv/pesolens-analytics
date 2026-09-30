# Security and demo scope

This is a single-user learning project using synthetic data.

## Implemented boundaries

- The HTTP server binds to loopback and accepts only local addresses or this Codespace's exact forwarded host and HTTPS Origin.
- Writes require bounded JSON objects. Foreign browser origins and unexpected hosts are rejected.
- Only index.html, guide.html, app.js, style.css, and icon.svg are served. Source, documentation, tests, and databases are private to the local filesystem.
- User-controlled text is escaped before HTML rendering. The server supplies a same-origin content security policy and disables embedding.
- SQLite queries are parameterized, foreign keys are enforced, and failed transactions roll back. Databases are excluded from Git.
- CSV exports neutralize leading spreadsheet-formula characters in text fields.

## Current limits

There are no user accounts, permissions, sessions, authentication, or production rate limits. Host/Origin validation does not provide user authentication; local processes can call the API. Keep Codespaces port visibility Private.

Before a public deployment, choose a production server/framework, add authentication and per-resource authorization, review CSRF and abuse controls, and define migrations, backups, monitoring, and deployment configuration where appropriate. AccessPath's invented measurements must not be used for actual navigation.

This document is a scope description, not a security audit.
