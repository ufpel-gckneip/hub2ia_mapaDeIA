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


async def test_map_researchers_dump_capped(client):
    # The dump endpoint must not allow pulling the whole researcher table:
    # the limit ceiling is bounded (a full-table limit is a 422), and an
    # unfiltered request returns a well-formed (capped) point list.
    r = await client.get("/api/map/researchers", params={"limit": 20000})
    assert r.status_code == 422, r.text

    r = await client.get("/api/map/researchers")
    assert r.status_code == 200, r.text
    assert isinstance(r.json()["points"], list)


async def test_map_researchers_bad_bbox_is_422(client):
    # A malformed bbox must fail loudly (422), not silently fall back to an
    # unfiltered pull. Both wrong-arity and non-numeric coords are rejected;
    # a well-formed bbox still succeeds.
    for bad in ("1,2,3", "a,b,c,d", "1,2,3,4,5"):
        r = await client.get("/api/map/researchers", params={"bbox": bad})
        assert r.status_code == 422, f"{bad!r} -> {r.status_code}: {r.text}"

    r = await client.get("/api/map/researchers", params={"bbox": "-54,-34,-34,6"})
    assert r.status_code == 200, r.text
    assert isinstance(r.json()["points"], list)


async def test_admin_requires_auth(client):
    r = await client.get("/api/admin/overview")
    assert r.status_code == 401


async def test_admin_forbidden_for_normal_user(registered_user, client):
    r = await client.get("/api/admin/overview", headers=registered_user["headers"])
    assert r.status_code == 403
