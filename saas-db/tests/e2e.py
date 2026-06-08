import httpx, sys

B = "http://127.0.0.1:8000/api/v1"
c = httpx.Client(base_url=B, timeout=10)
P, F = 0, 0
def check(name, cond, extra=""):
    global P, F
    if cond: P += 1; print(f"  PASS  {name}")
    else: F += 1; print(f"  FAIL  {name}  {extra}")

print("== Registration ==")
r = c.post("/auth/register", json={"email":"alice@acme.io","password":"Sup3rSecret!","full_name":"Alice"})
check("register alice 201", r.status_code==201, r.text)
r2 = c.post("/auth/register", json={"email":"alice@acme.io","password":"Sup3rSecret!"})
check("duplicate register 409", r2.status_code==409, r2.text)
r3 = c.post("/auth/register", json={"email":"bob@acme.io","password":"BobPassw0rd!","full_name":"Bob"})
check("register bob 201", r3.status_code==201, r3.text)
c.post("/auth/register", json={"email":"charlie@evil.io","password":"Charlie123!","full_name":"Charlie"})

print("== Login ==")
r = c.post("/auth/login", json={"email":"alice@acme.io","password":"wrong"})
check("bad password 401", r.status_code==401, r.text)
r = c.post("/auth/login", json={"email":"alice@acme.io","password":"Sup3rSecret!"})
check("login alice 200", r.status_code==200, r.text)
tok = r.json(); A = tok["access_token"]; AR = tok["refresh_token"]
check("token has expires_in", tok.get("expires_in")==900, tok)
ah = {"Authorization": f"Bearer {A}"}

print("== Auth guards ==")
check("me without token 401", c.get("/users/me").status_code==401)
r = c.get("/users/me", headers=ah)
check("me 200", r.status_code==200, r.text)
check("me no companies yet", r.json()["memberships"]==[], r.text)

print("== Company creation & membership ==")
r = c.post("/companies", headers=ah, json={"name":"Acme Inc","slug":"acme"})
check("create company 201", r.status_code==201, r.text)
cid = r.json()["id"]
r = c.get("/companies", headers=ah)
check("list my companies =1", len(r.json())==1 and r.json()[0]["role_slug"]=="owner", r.text)
r = c.get(f"/companies/{cid}/me", headers=ah)
check("role context owner", r.json()["role_slug"]=="owner", r.text)
check("owner has members:invite", "members:invite" in r.json()["permissions"], r.json())

# add bob
r = c.post(f"/companies/{cid}/members", headers=ah, json={"email":"bob@acme.io","role_slug":"member"})
check("add bob 201", r.status_code==201, r.text)
r = c.post(f"/companies/{cid}/members", headers=ah, json={"email":"bob@acme.io","role_slug":"member"})
check("add bob dup 409", r.status_code==409, r.text)
r = c.get(f"/companies/{cid}/members", headers=ah)
check("members list =2", len(r.json())==2, r.text)

print("== Tenant isolation / RBAC ==")
# charlie is not a member
rc = c.post("/auth/login", json={"email":"charlie@evil.io","password":"Charlie123!"}).json()
ch = {"Authorization": f"Bearer {rc['access_token']}"}
check("charlie role context 403", c.get(f"/companies/{cid}/me", headers=ch).status_code==403)
check("charlie members 403", c.get(f"/companies/{cid}/members", headers=ch).status_code==403)
# bob is a 'member' role -> lacks members:invite
rb = c.post("/auth/login", json={"email":"bob@acme.io","password":"BobPassw0rd!"}).json()
bh = {"Authorization": f"Bearer {rb['access_token']}"}
check("bob role member", c.get(f"/companies/{cid}/me", headers=bh).json()["role_slug"]=="member")
check("bob lacks invite -> 403 on members", c.get(f"/companies/{cid}/members", headers=bh).status_code==403)

print("== Refresh rotation ==")
r = c.post("/auth/refresh", json={"refresh_token": AR})
check("refresh 200", r.status_code==200, r.text)
newAR = r.json()["refresh_token"]
check("rotated token differs", newAR != AR)
check("old refresh reuse 401", c.post("/auth/refresh", json={"refresh_token": AR}).status_code==401)

print("== Password reset ==")
r = c.post("/auth/password-reset/request", json={"email":"bob@acme.io"})
check("reset request 202", r.status_code==202, r.text)
rt = r.json()["dev_token"]; check("dev reset token present", bool(rt))
check("reset confirm 204", c.post("/auth/password-reset/confirm", json={"token":rt,"new_password":"BobN3wPass!"}).status_code==204)
check("old pw now fails", c.post("/auth/login", json={"email":"bob@acme.io","password":"BobPassw0rd!"}).status_code==401)
check("new pw works", c.post("/auth/login", json={"email":"bob@acme.io","password":"BobN3wPass!"}).status_code==200)
check("reset token single-use 401", c.post("/auth/password-reset/confirm", json={"token":rt,"new_password":"x12345678"}).status_code==401)

print("== Email verification ==")
r = c.post("/auth/verify-email/request", json={"email":"alice@acme.io"})
vt = r.json()["dev_token"]; check("verify token present", bool(vt))
check("verify confirm 204", c.post("/auth/verify-email/confirm", json={"token":vt}).status_code==204)

print("== Logout ==")
check("logout 204", c.post("/auth/logout", json={"refresh_token": newAR}).status_code==204)
check("refresh after logout 401", c.post("/auth/refresh", json={"refresh_token": newAR}).status_code==401)

print(f"\nRESULT: {P} passed, {F} failed")
sys.exit(1 if F else 0)
