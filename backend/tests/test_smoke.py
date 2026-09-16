"""End-to-end smoke tests: health, auth flow, a read path, and admin authz.

These exercise the wiring (routing, auth backend, DB session, migrations) rather
than business logic. They run against an empty-but-migrated database, so read
endpoints are asserted on shape, not on seeded rows.
"""

import pytest


async def test_health(client):
    r = await client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


async def test_register_login_me(client):
    creds = {"email": "alice@example.com", "password": "Str0ng-Passw0rd!"}

    r = await client.post("/auth/register", json=creds)
    assert r.status_code in (200, 201), r.text
    assert r.json()["email"] == creds["email"]

    r = await client.post(
        "/auth/jwt/login",
        data={"username": creds["email"], "password": creds["password"]},
    )
    assert r.status_code == 200, r.text
    token = r.json()["access_token"]

    r = await client.get("/users/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json()["email"] == creds["email"]


async def test_login_rejects_bad_password(client):
    await client.post(
        "/auth/register",
        json={"email": "bob@example.com", "password": "Str0ng-Passw0rd!"},
    )
    r = await client.post(
        "/auth/jwt/login",
        data={"username": "bob@example.com", "password": "wrong"},
    )
    assert r.status_code == 400


async def test_researchers_list_shape(client):
    r = await client.get("/api/researchers", params={"limit": 5})
    assert r.status_code == 200, r.text
    body = r.json()
    assert set(body) >= {"total", "items"}
    assert isinstance(body["items"], list)


@pytest.mark.parametrize("min_degree", [0, 5])
async def test_graph_shape(client, min_degree):
    r = await client.get("/api/graph", params={"min_degree": min_degree})
    assert r.status_code == 200, r.text
    body = r.json()
    assert isinstance(body["nodes"], list)
    assert isinstance(body["edges"], list)
    # Every returned edge must connect two surviving (degree-filtered) nodes;
    # the endpoint filters this in SQL rather than shipping every edge.
    ids = {n["id"] for n in body["nodes"]}
    for e in body["edges"]:
        assert e["source"] in ids and e["target"] in ids


async def test_admin_requires_auth(client):
    r = await client.get("/api/admin/overview")
    assert r.status_code == 401


async def test_admin_forbidden_for_normal_user(registered_user, client):
    r = await client.get("/api/admin/overview", headers=registered_user["headers"])
    assert r.status_code == 403
