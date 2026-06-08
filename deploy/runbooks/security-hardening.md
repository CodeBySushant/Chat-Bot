# Security Hardening

## Transport & headers
- **HSTS:** `max-age=63072000; includeSubDomains; preload` on all HTTPS hosts.
- **TLS:** 1.2/1.3 only, intermediate cipher suite, OCSP stapling, session tickets off.
- **HTTP→HTTPS:** 301 redirect for everything except the ACME challenge path.

## CSP
- **Dashboard (`app.example.com`):** strict — `default-src 'self'`,
  `script-src 'self'`, `frame-ancestors 'none'`, `connect-src 'self' https://api.example.com`.
  No `unsafe-inline` scripts.
- **Widget (`cdn.example.com`):** the bundle is designed to be embedded on third
  party sites, so it ships no inline scripts and is served with `Access-Control-Allow-Origin: *`
  for the static JS only. It runs inside the host page; embedders set their own CSP.
- Plus `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`,
  `Referrer-Policy: strict-origin-when-cross-origin`, `Permissions-Policy` lockdown.

## Cookies & sessions
- Auth uses **Bearer tokens** (not cookies), so there is no ambient authority and
  CSRF surface is minimal. If cookie sessions are added, set
  `Secure; HttpOnly; SameSite=Strict` and a separate CSRF token (double-submit).

## CORS
- API CORS is permissive at the edge for the **public widget** only and uses
  `allow_credentials=false` (safe with Bearer). The widget additionally enforces a
  **per-chatbot domain allowlist** in the application layer (Origin/Referer check).
- Dashboard origins are explicit (`CORS_ORIGINS`).

## CSRF
- Token auth in headers → no cookie-based CSRF. Mutating endpoints require the
  `Authorization` header; browsers cannot attach it cross-site automatically.

## SSRF protections (crawler is the main surface)
- Crawler resolves and **blocks private/loopback/link-local/metadata ranges**
  (`127.0.0.0/8`, `10/8`, `172.16/12`, `192.168/16`, `169.254/16`, `::1`,
  `fc00::/7`), enforces an allowlist of schemes (`http`/`https` only), caps
  redirects, honors robots, and times out. Run the crawler/worker in a network
  segment with **no access to internal services or the cloud metadata endpoint**
  (block `169.254.169.254` at the egress firewall; use IMDSv2).

## Rate limiting & DDoS
- **Edge (nginx):** per-IP `limit_req` zones — api 30r/s, auth 5r/s, widget 20r/s —
  plus `limit_conn`. Tight `client_max_body_size` (25m) and timeouts.
- **App:** in-process fixed-window limiter on auth + widget message endpoints
  (move to Redis-backed for multi-instance — see scalability).
- **Network:** front with a CDN/WAF (Cloudflare/AWS WAF + Shield) for L3/4 and
  L7 DDoS, bot mitigation, and geo/ASN rules. Enable SYN cookies on hosts.

## Secrets & access
- `_FILE` secret injection; no secrets in images/env/logs.
- Distinct DB roles (`app_rw` RLS-bound, `app_admin` BYPASSRLS only where needed).
- Containers run **non-root**, `no-new-privileges`, `cap_drop: ALL`, read-only
  rootfs where possible.
- Image scanning (Trivy) + dependency audit (pip-audit) + secret scan (gitleaks) in CI.
