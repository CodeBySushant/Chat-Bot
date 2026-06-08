# Security Checklist (pre-launch + quarterly)

## Network & edge
- [ ] All traffic HTTPS; HTTP redirects; HSTS + preload.
- [ ] WAF/CDN enabled; rate limits (api/auth/widget) active; `limit_conn` set.
- [ ] Datastores on an `internal` network with no public ingress.
- [ ] Egress firewall blocks the cloud metadata IP from the crawler/worker network.

## Application
- [ ] CSP/headers present (verify with securityheaders.com / curl -I).
- [ ] Bearer-token auth; no cookie CSRF surface; tokens short-lived + refresh rotation.
- [ ] Widget domain allowlist enforced; CORS `allow_credentials=false` at edge.
- [ ] SSRF guard in crawler (private-range + scheme allowlist) tested.
- [ ] Input size limits (uploads 25m, request body) enforced.

## Identity & access
- [ ] RBAC enforced; least-privilege roles; admin gated by `is_superuser`.
- [ ] DB roles split (RLS `app_rw` vs `app_admin` BYPASSRLS).
- [ ] SSH/deploy keys scoped; production environment requires approval.

## Secrets
- [ ] No secrets in git/images/logs (gitleaks clean).
- [ ] `_FILE` injection in use; rotation schedule documented + tested.

## Supply chain
- [ ] Trivy (image+fs) and pip-audit clean of CRITICAL/HIGH; base images pinned.
- [ ] Containers non-root, `no-new-privileges`, `cap_drop: ALL`, read-only rootfs.

## Data protection
- [ ] Backups encrypted (KMS/age) at rest; restore tested.
- [ ] PII handling reviewed; deletion path for tenant/user data; audit logs retained.
