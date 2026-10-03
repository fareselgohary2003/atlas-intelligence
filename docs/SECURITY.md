# Security

| Control | Implementation | Verified here? |
|---|---|---|
| Sessions | httpOnly session cookie (HS256, `app/core/tokens.py`; only HS256 accepted, `exp`/`sub`/`jti` mandatory), `Secure` via `COOKIE_SECURE`, SameSite | token logic: yes; cookie wiring: no |
| CSRF | double-submit token HMAC-bound to the session id + Origin check on unsafe cookie requests; Bearer clients exempt | logic: yes; HTTP: no |
| Rate limiting | per-IP and per-account login limits, global API limit; Redis fixed window with in-process fallback if Redis fails | logic: yes; Redis: no |
| RBAC | owner/admin/researcher/viewer; non-members get 404, wrong role 403 | integration tests written, not run |
| Isolation | every repository query filters `research_id`; scope comes from the engine (never tool arguments); composite FKs; non-revealing error messages | service level: yes; DB level: no |
| SSRF | scheme/port allow-list, no credentials, legacy-IP forms, IPv6 (mapped/6to4/NAT64/Teredo), all resolved IPs checked, IP pinning, every redirect hop re-validated | yes (incl. real sockets on loopback) |
| Fetch limits | size caps incl. decompression bombs, timeouts, content-type allow-list | yes |
| Secrets | never in events/logs/API; redaction by key name and pattern; settings page shows booleans only | yes |
| Injection of reasoning | event whitelist drops unknown fields | yes |
| Audit | login, research lifecycle, task start/fail, report generate/export, member changes; immutable (Postgres trigger) | row creation: no |

## Mutation checks performed (each broke tests, then restored)
SSRF IP check, redirect re-validation, quote grounding, research scoping, agent grants, verification rules, JWT algorithm check (a surviving mutation led to a new test), CSRF verification, token expiry, rate limiter, log redaction, frontend CSRF header.

## Limitations
- Sessions are stateless: logout clears cookies but there is no server-side revocation list.
- No password reset, email verification or 2FA. No security headers (CSP, HSTS) middleware yet.
- Redis outage degrades rate limiting to per-process counters.
- Log redaction is pattern-based and best-effort.
- DNS is resolved with the system resolver; a resolver that lies consistently is out of scope.
