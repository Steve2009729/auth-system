import pytest
from httpx import AsyncClient
from app.main import app


@pytest.mark.asyncio
async def test_register_success(client: AsyncClient, test_user_data):
    """Test successful user registration."""
    response = await client.post("/auth/register", json=test_user_data)
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == test_user_data["email"]
    assert data["username"] == test_user_data["username"]
    assert data["is_verified"] == False


@pytest.mark.asyncio
async def test_register_duplicate_email(client: AsyncClient, test_user_data):
    """Test registration with duplicate email."""
    # First registration
    await client.post("/auth/register", json=test_user_data)

    # Second registration with same email
    response = await client.post("/auth/register", json={**test_user_data, "username": "different"})
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_register_duplicate_username(client: AsyncClient, test_user_data):
    """Test registration with duplicate username."""
    # First registration
    await client.post("/auth/register", json=test_user_data)

    # Second registration with same username
    response = await client.post("/auth/register", json={**test_user_data, "email": "different@example.com"})
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_login_success(client: AsyncClient, test_user_data):
    """Test successful login."""
    # Register first
    await client.post("/auth/register", json=test_user_data)

    # Then login
    response = await client.post(
        "/auth/login",
        json={"email": test_user_data["email"], "password": test_user_data["password"]}
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"
    assert data["requires_2fa"] == False


@pytest.mark.asyncio
async def test_login_invalid_password(client: AsyncClient, test_user_data):
    """Test login with invalid password."""
    # Register first
    await client.post("/auth/register", json=test_user_data)

    # Try login with wrong password
    response = await client.post(
        "/auth/login",
        json={"email": test_user_data["email"], "password": "WrongPassword123!"}
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_login_nonexistent_user(client: AsyncClient):
    """Test login with non-existent user."""
    response = await client.post(
        "/auth/login",
        json={"email": "nonexistent@example.com", "password": "AnyPassword123!"}
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_refresh_token_success(client: AsyncClient, test_user_data):
    """Test successful token refresh."""
    # Register and login
    await client.post("/auth/register", json=test_user_data)
    login_response = await client.post(
        "/auth/login",
        json={"email": test_user_data["email"], "password": test_user_data["password"]}
    )
    refresh_token = login_response.json()["refresh_token"]

    # Refresh token
    response = await client.post(
        "/auth/refresh",
        json={"refresh_token": refresh_token}
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data


@pytest.mark.asyncio
async def test_refresh_token_invalid(client: AsyncClient):
    """Test refresh with invalid token."""
    response = await client.post(
        "/auth/refresh",
        json={"refresh_token": "invalid_token"}
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_health_check(client: AsyncClient):
    """Test health check endpoint."""
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
