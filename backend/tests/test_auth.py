"""Password policy (TODO #5): register/reset reject weak passwords.

fastapi-users turns an InvalidPasswordException into HTTP 400 on /auth/register.
"""


async def test_register_rejects_short_password(client):
    r = await client.post(
        "/auth/register",
        json={"email": "shorty@example.com", "password": "Ab1!xyz"},  # 7 chars
    )
    assert r.status_code == 400, r.text


async def test_register_rejects_email_in_password(client):
    email = "carol@example.com"
    r = await client.post(
        "/auth/register",
        json={"email": email, "password": f"{email}-extra"},  # long enough, but contains email
    )
    assert r.status_code == 400, r.text


async def test_register_accepts_strong_password(client):
    r = await client.post(
        "/auth/register",
        json={"email": "dave@example.com", "password": "Str0ng-Passw0rd!"},
    )
    assert r.status_code in (200, 201), r.text
    assert r.json()["email"] == "dave@example.com"


# ── Access + refresh tokens (TODO #6) ──


async def _register_and_login(client, email):
    pw = "Str0ng-Passw0rd!"
    await client.post("/auth/register", json={"email": email, "password": pw})
    r = await client.post("/auth/jwt/login", data={"username": email, "password": pw})
    assert r.status_code == 200, r.text
    return r.json()


async def test_login_returns_token_pair(client):
    tokens = await _register_and_login(client, "erin@example.com")
    assert tokens["access_token"] and tokens["refresh_token"]
    assert tokens["access_token"] != tokens["refresh_token"]


async def test_refresh_issues_working_access_token(client):
    tokens = await _register_and_login(client, "frank@example.com")
    r = await client.post("/auth/jwt/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert r.status_code == 200, r.text
    new_access = r.json()["access_token"]

    me = await client.get("/users/me", headers={"Authorization": f"Bearer {new_access}"})
    assert me.status_code == 200
    assert me.json()["email"] == "frank@example.com"


async def test_access_token_is_not_a_valid_refresh_token(client):
    tokens = await _register_and_login(client, "grace@example.com")
    # Presenting the access token to /refresh must fail (distinct audience).
    r = await client.post("/auth/jwt/refresh", json={"refresh_token": tokens["access_token"]})
    assert r.status_code == 401, r.text


async def test_refresh_token_is_not_a_valid_bearer(client):
    tokens = await _register_and_login(client, "heidi@example.com")
    # Presenting the refresh token as a Bearer access token must fail.
    r = await client.get(
        "/users/me", headers={"Authorization": f"Bearer {tokens['refresh_token']}"}
    )
    assert r.status_code == 401, r.text
