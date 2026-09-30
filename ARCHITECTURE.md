# PesoLens architecture

Browser (index.html + app.js) → same-origin HTTP API (run.py) → domain rules (app.py) → SQLite via core.py.

## Files and responsibilities

| File | Responsibility |
| --- | --- |
| run.py | Loopback server, exact Codespaces host/origin checks, JSON validation, safe static allowlist and HTTP error mapping |
| app.py | Expense analytics rules and API dispatch |
| core.py | Explicit API errors, input validation and SQLite connection/transaction helpers |
| app.js | Forms, fetch calls, escaped output, success/error feedback |
| index.html / style.css | Keyboard-accessible shell and responsive dashboard |
| test_business.py / test_http.py | Isolated domain tests and actual HTTP boundary checks |

## Data flow

A form sends JSON to `/api/peso/…`. The server validates the request shape before calling the domain handler. Domain errors become explicit HTTP responses. The interface refreshes from saved state after successful changes, rather than guessing the result. `/api/health` confirms the running project's identity.

## Main design decision

Read README.md's data model and design choice sections. Trace one successful operation and one rejected operation through the frontend, API, and domain code. This repository includes the helper code it needs; it never imports graduate-portfolio or the other four projects.

## Runtime limits

SQLite fits this local single-user workload. A production service would need authentication, authorization, migrations, backups, and a production HTTP server. The bundled server listens only on loopback; Codespaces exposes it through its own private forwarded port.
