import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_list_sessions(client: AsyncClient, test_user_data):
    """Test listing user sessions."""
    # Register and login
    await client.post("/auth/register", json=test_user_data)
    login_response = await client.post(
        "/auth/login",
        json={"email": test_user_data["email"], "password": test_user_data["password"]}
    )
    access_token = login_response.json()["access_token"]

    # List sessions
    response = await client.get(
        "/sessions",
        headers={"Authorization": f"Bearer {access_token}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) > 0


@pytest.mark.asyncio
async def test_list_sessions_without_auth(client: AsyncClient):
    """Test listing sessions without authentication."""
    response = await client.get("/sessions")
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_logout(client: AsyncClient, test_user_data):
    """Test logout."""
    # Register and login
    await client.post("/auth/register", json=test_user_data)
    login_response = await client.post(
        "/auth/login",
        json={"email": test_user_data["email"], "password": test_user_data["password"]}
    )
    access_token = login_response.json()["access_token"]

    # Logout
    response = await client.post(
        "/auth/logout",
        headers={"Authorization": f"Bearer {access_token}"}
    )
    assert response.status_code == 204


@pytest.mark.asyncio
async def test_logout_all(client: AsyncClient, test_user_data):
    """Test logout from all devices."""
    # Register and login
    await client.post("/auth/register", json=test_user_data)
    login_response = await client.post(
        "/auth/login",
        json={"email": test_user_data["email"], "password": test_user_data["password"]}
    )
    access_token = login_response.json()["access_token"]

    # Logout all
    response = await client.post(
        "/auth/logout/all",
        headers={"Authorization": f"Bearer {access_token}"}
    )
    assert response.status_code == 204
