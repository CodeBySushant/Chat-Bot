# Secrets Management Strategy

## Principles
- **No secrets in images or git.** Images are built from source only; secrets are
  injected at runtime. `.env` and `secrets/*` are git-ignored.
- **`_FILE` convention.** The app reads `DATABASE_URL_FILE`, `JWT_SECRET_KEY_FILE`,
  etc. (Docker/Swarm secrets mounted at `/run/secrets/*`). A tiny settings hook
  reads `*_FILE` and overrides the plain var. Never pass secrets as plain env in
  prod.
- **Least privilege.** `app_rw` is RLS-bound; only the worker/admin paths use
  `app_admin` (BYPASSRLS). DB users are distinct from the superuser.

## Environment strategy (per stage)
| Stage      | Store                        | Injection |
|------------|------------------------------|-----------|
| local dev  | `.env` + `secrets/*` files   | docker compose |
| CI         | GitHub Actions Secrets       | `env:` / OIDC, masked in logs |
| staging    | AWS Secrets Manager          | entrypoint fetch -> `/run/secrets` |
| production | AWS Secrets Manager or Vault | sidecar/agent injects at boot |

## Backends

### GitHub Secrets (CI/CD)
- `DEPLOY_SSH_KEY`, `STAGING_HOST`, `PROD_HOST`, `DEPLOY_USER`, registry token.
- Use **environments** (`staging`, `production`) with required reviewers for prod.
- Prefer **OIDC federation** to AWS over long-lived keys (`aws-actions/configure-aws-credentials`).

### AWS Secrets Manager
- One secret per service: `chatbot/prod/api`, `chatbot/prod/worker`.
- Boot fetch in the entrypoint:
  `aws secretsmanager get-secret-value --secret-id chatbot/prod/api | jq -r .SecretString | ... > /run/secrets/...`
- Rotation via Lambda rotation functions (RDS supports native rotation).

### HashiCorp Vault
- KV v2 at `secret/chatbot/prod/*`; dynamic DB creds via the `database` secrets
  engine (short-lived Postgres credentials, auto-revoked).
- Inject with the Vault Agent sidecar + `vault.hashicorp.com/agent-inject` annotations
  (K8s) or `vault agent` templating (Compose host).

## Rotation strategy
| Secret              | Frequency | Method |
|---------------------|-----------|--------|
| JWT signing key     | 90 days   | dual-key: add new `kid`, sign with new, verify both, retire old after max token TTL |
| DB passwords        | 30–90 days| Vault dynamic creds (preferred) or Secrets Manager rotation Lambda |
| Provider API keys   | on leak / 180 days | rotate in provider dashboard -> update secret -> rolling restart |
| Webhook signing     | on leak   | rotate, support old+new during overlap window |

See `rotate-secrets.sh` for the JWT dual-key + DB rotation helper.
