"""Security-hardening test suite.

Two modes (chosen by argv[1]):
  * core      -> refresh-family reuse detection, tenant-gate status checks,
                 JWT iss/aud/expiry/alg-none/type validation, and it performs
                 the six auditable actions so the runner can verify audit rows.
  * ratelimit -> verifies login/register/refresh/password-reset throttling.

Run against a live server (see tests/run_hardening.sh).
"""
from __future__ import annotations

import base64
import json
import subprocess
import sys
import time
import uuid
from datetime import datetime, timedelta, timezone

import httpx
import jwt

from app.core.config import settings

BASE = "http://127.0.0.1:8000/api/v1"
P = {"pass": 0, "fail": 0}


def check(name, cond, extra=""):
    if cond:
        P["pass"] += 1
        print(f"  PASS  {name}")
    else:
        P["fail"] += 1
        print(f"  FAIL  {name}  {extra}")


def psql(sql: str) -> str:
    out = subprocess.run(
        [
            "su", "postgres", "-c",
            f"/usr/lib/postgresql/16/bin/psql -h /tmp -p 5432 -d chatbot_saas -t -A -c \"{sql}\"",
        ],
        capture_output=True, text=True,
    )
    return out.stdout.strip()


def cleanup():
    psql("DELETE FROM companies WHERE slug='acme';")
    psql(
        "DELETE FROM users WHERE email IN "
        "('alice@acme.io','bob@acme.io','carol@acme.io');"
    )


# --------------------------------------------------------------------------- #
# JWT crafting helpers (use the server's configured secret/iss/aud)
# --------------------------------------------------------------------------- #
def _base_claims(**over):
    now = datetime.now(timezone.utc)
    claims = {
        "sub": str(uuid.uuid4()),
        "type": "access",
        "iss": settings.JWT_ISSUER,
        "aud": settings.JWT_AUDIENCE,
        "iat": int(now.timestamp()),
        "nbf": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=5)).timestamp()),
        "jti": str(uuid.uuid4()),
    }
    claims.update(over)
    return claims


def _sign(claims):
    return jwt.encode(claims, settings.JWT_SECRET_KEY, algorithm="HS256")


def _alg_none_token(claims):
    def b64(d):
        return base64.urlsafe_b64encode(json.dumps(d).encode()).rstrip(b"=").decode()
    return f"{b64({'alg': 'none', 'typ': 'JWT'})}.{b64(claims)}."


def core():
    c = httpx.Client(base_url=BASE, timeout=10)
    cleanup()

    # --- seed users ---
    c.post("/auth/register", json={"email": "alice@acme.io", "password": "Sup3rSecret!", "full_name": "Alice"})
    c.post("/auth/register", json={"email": "bob@acme.io", "password": "BobPassw0rd!", "full_name": "Bob"})

    alice = c.post("/auth/login", json={"email": "alice@acme.io", "password": "Sup3rSecret!"}).json()
    ah = {"Authorization": f"Bearer {alice['access_token']}"}

    print("== JWT issuer/audience/expiry validation ==")
    check("valid token -> 200", c.get("/users/me", headers=ah).status_code == 200)
    real_sub = jwt.decode(alice["access_token"], settings.JWT_SECRET_KEY,
                          algorithms=["HS256"], audience=settings.JWT_AUDIENCE,
                          issuer=settings.JWT_ISSUER)["sub"]
    bad = {
        "expired": _sign(_base_claims(sub=real_sub, exp=int((datetime.now(timezone.utc) - timedelta(minutes=1)).timestamp()))),
        "wrong audience": _sign(_base_claims(sub=real_sub, aud="someone-else")),
        "wrong issuer": _sign(_base_claims(sub=real_sub, iss="evil-issuer")),
        "wrong type": _sign(_base_claims(sub=real_sub, type="refresh")),
        "alg=none": _alg_none_token(_base_claims(sub=real_sub)),
    }
    for label, tok in bad.items():
        code = c.get("/users/me", headers={"Authorization": f"Bearer {tok}"}).status_code
        check(f"{label} -> 401", code == 401, f"got {code}")

    print("== Company + member (auditable actions) ==")
    cid = c.post("/companies", headers=ah, json={"name": "Acme Inc", "slug": "acme"}).json()["id"]
    add = c.post(f"/companies/{cid}/members", headers=ah, json={"email": "bob@acme.io", "role_slug": "member"})
    check("add bob 201", add.status_code == 201, add.text)
    bob_uid = add.json()["user_id"]

    print("== Tenant gate: active member + active company ==")
    bob = c.post("/auth/login", json={"email": "bob@acme.io", "password": "BobPassw0rd!"}).json()
    bh = {"Authorization": f"Bearer {bob['access_token']}"}
    check("active member -> 200", c.get(f"/companies/{cid}/me", headers=bh).status_code == 200)
    # suspend the member
    psql(f"UPDATE company_members SET status='suspended' WHERE company_id='{cid}' AND user_id='{bob_uid}';")
    check("suspended member -> 403", c.get(f"/companies/{cid}/me", headers=bh).status_code == 403)
    # reactivate bob, then suspend the company
    psql(f"UPDATE company_members SET status='active' WHERE company_id='{cid}' AND user_id='{bob_uid}';")
    psql(f"UPDATE companies SET status='suspended' WHERE id='{cid}';")
    check("suspended company -> 403 (owner)", c.get(f"/companies/{cid}/me", headers=ah).status_code == 403)
    psql(f"UPDATE companies SET status='active' WHERE id='{cid}';")

    print("== Refresh token family reuse detection ==")
    r0 = c.post("/auth/login", json={"email": "bob@acme.io", "password": "BobPassw0rd!"}).json()["refresh_token"]
    r1 = c.post("/auth/refresh", json={"refresh_token": r0}).json()["refresh_token"]
    r2 = c.post("/auth/refresh", json={"refresh_token": r1}).json()["refresh_token"]
    r3resp = c.post("/auth/refresh", json={"refresh_token": r2})
    check("active descendant works pre-reuse", r3resp.status_code == 200)
    r3 = r3resp.json()["refresh_token"]  # currently the only active token in the family
    # reuse the long-revoked r0 -> reuse detection revokes the whole family
    reuse = c.post("/auth/refresh", json={"refresh_token": r0})
    check("reuse of revoked token -> 401", reuse.status_code == 401, reuse.text)
    # the still-active descendant r3 must now be dead too
    after = c.post("/auth/refresh", json={"refresh_token": r3})
    check("active descendant revoked after reuse -> 401", after.status_code == 401, after.text)

    print("== Remaining auditable actions ==")
    # logout (fresh session so as not to interfere)
    fresh = c.post("/auth/login", json={"email": "alice@acme.io", "password": "Sup3rSecret!"}).json()
    check("logout 204", c.post("/auth/logout", json={"refresh_token": fresh["refresh_token"]}).status_code == 204)
    # password reset for bob
    rt = c.post("/auth/password-reset/request", json={"email": "bob@acme.io"}).json()["dev_token"]
    check("reset confirm 204", c.post("/auth/password-reset/confirm", json={"token": rt, "new_password": "BobN3wPass!"}).status_code == 204)
    # email verification for alice
    vt = c.post("/auth/verify-email/request", json={"email": "alice@acme.io"}).json()["dev_token"]
    check("verify confirm 204", c.post("/auth/verify-email/confirm", json={"token": vt}).status_code == 204)

    print("== Audit rows written (activity_logs) ==")
    for action in ["user.login", "user.logout", "user.password_reset",
                   "user.email_verified", "company.created", "member.created"]:
        n = psql(f"SELECT count(*) FROM activity_logs WHERE action='{action}' "
                 f"AND created_at > now() - interval '5 minutes';")
        check(f"audit '{action}' >= 1", n.isdigit() and int(n) >= 1, f"count={n}")

    cleanup()


def ratelimit():
    c = httpx.Client(base_url=BASE, timeout=10)
    cleanup()
    # limits set low via env for this run; window 60s
    print("== Rate limiting ==")

    # register: distinct emails so only the limiter (not 409) triggers
    codes = [c.post("/auth/register", json={"email": f"rl{i}@acme.io", "password": "Passw0rd!!"}).status_code
             for i in range(settings.RATE_LIMIT_REGISTER_MAX + 2)]
    check("register eventually 429", 429 in codes, f"codes={codes}")

    # login: repeated bad logins from same IP
    codes = [c.post("/auth/login", json={"email": "nope@acme.io", "password": "x"}).status_code
             for _ in range(settings.RATE_LIMIT_LOGIN_MAX + 2)]
    check("login eventually 429", 429 in codes, f"codes={codes}")
    last = c.post("/auth/login", json={"email": "nope@acme.io", "password": "x"})
    check("429 carries Retry-After", last.headers.get("Retry-After") is not None, dict(last.headers))

    # password reset request
    codes = [c.post("/auth/password-reset/request", json={"email": "whoever@acme.io"}).status_code
             for _ in range(settings.RATE_LIMIT_PASSWORD_RESET_MAX + 2)]
    check("password-reset eventually 429", 429 in codes, f"codes={codes}")

    # refresh
    codes = [c.post("/auth/refresh", json={"refresh_token": "bogus"}).status_code
             for _ in range(settings.RATE_LIMIT_REFRESH_MAX + 2)]
    check("refresh eventually 429", 429 in codes, f"codes={codes}")

    psql("DELETE FROM users WHERE email LIKE 'rl%@acme.io';")


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "core"
    {"core": core, "ratelimit": ratelimit}[mode]()
    print(f"\nRESULT [{mode}]: {P['pass']} passed, {P['fail']} failed")
    sys.exit(1 if P["fail"] else 0)
