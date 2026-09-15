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
