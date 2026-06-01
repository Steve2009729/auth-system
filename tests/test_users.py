import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_get_current_user_profile(client: AsyncClient, test_user_data):
    """Test getting current user profile."""
    # Register and login
    await client.post("/auth/register", json=test_user_data)
    login_response = await client.post(
        "/auth/login",
        json={"email": test_user_data["email"], "password": test_user_data["password"]}
    )
    access_token = login_response.json()["access_token"]

    # Get profile
    response = await client.get(
        "/users/me",
        headers={"Authorization": f"Bearer {access_token}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == test_user_data["email"]
    assert data["username"] == test_user_data["username"]


@pytest.mark.asyncio
async def test_get_current_user_without_auth(client: AsyncClient):
    """Test getting current user without authentication."""
    response = await client.get("/users/me")
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_update_user_profile(client: AsyncClient, test_user_data):
    """Test updating user profile."""
    # Register and login
    await client.post("/auth/register", json=test_user_data)
    login_response = await client.post(
        "/auth/login",
        json={"email": test_user_data["email"], "password": test_user_data["password"]}
    )
    access_token = login_response.json()["access_token"]

    # Update profile
    response = await client.patch(
        "/users/me",
        json={"full_name": "Updated Name", "avatar_url": "https://example.com/avatar.jpg"},
        headers={"Authorization": f"Bearer {access_token}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["full_name"] == "Updated Name"
    assert data["avatar_url"] == "https://example.com/avatar.jpg"


@pytest.mark.asyncio
async def test_get_user_permissions(client: AsyncClient, test_user_data):
    """Test getting user permissions."""
    # Register and login
    await client.post("/auth/register", json=test_user_data)
    login_response = await client.post(
        "/auth/login",
        json={"email": test_user_data["email"], "password": test_user_data["password"]}
    )
    access_token = login_response.json()["access_token"]

    # Get permissions
    response = await client.get(
        "/users/me/permissions",
        headers={"Authorization": f"Bearer {access_token}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data["permissions"], list)
