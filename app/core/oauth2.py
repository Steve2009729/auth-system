import logging
from app.config import settings

logger = logging.getLogger(__name__)

_PLACEHOLDER = {"your-google-client-id", "your-google-client-secret",
                "your-github-client-id", "your-github-client-secret", ""}


def google_enabled() -> bool:
    """True if Google OAuth credentials are configured."""
    return (
        settings.GOOGLE_CLIENT_ID not in _PLACEHOLDER
        and settings.GOOGLE_CLIENT_SECRET not in _PLACEHOLDER
    )


def github_enabled() -> bool:
    """True if GitHub OAuth credentials are configured."""
    return (
        settings.GITHUB_CLIENT_ID not in _PLACEHOLDER
        and settings.GITHUB_CLIENT_SECRET not in _PLACEHOLDER
    )


class GoogleOAuth:
    """Google OAuth2 client. Only usable when google_enabled() is True."""

    def __init__(self):
        if not google_enabled():
            logger.warning(
                "Google OAuth is not configured. Set GOOGLE_CLIENT_ID and "
                "GOOGLE_CLIENT_SECRET in your .env to enable Google login."
            )

    def _client(self):
        from authlib.integrations.httpx_client import AsyncOAuth2Client
        return AsyncOAuth2Client(
            client_id=settings.GOOGLE_CLIENT_ID,
            client_secret=settings.GOOGLE_CLIENT_SECRET,
            redirect_uri=settings.GOOGLE_REDIRECT_URI,
        )

    def get_authorization_url(self):
        """Get authorization URL for Google login."""
        client = self._client()
        uri, state = client.create_authorization_url(
            "https://accounts.google.com/o/oauth2/v2/auth",
            scopes=["openid", "email", "profile"],
        )
        return uri, state

    async def get_access_token(self, code: str, state: str):
        """Exchange authorization code for access token."""
        client = self._client()
        token = await client.fetch_token(
            "https://oauth2.googleapis.com/token",
            code=code,
        )
        return token

    async def get_user_info(self, token) -> dict:
        """Get user info from Google."""
        client = self._client()
        async with client as c:
            resp = await c.get(
                "https://openidconnect.googleapis.com/v1/userinfo",
                token=token,
            )
            return resp.json()


class GitHubOAuth:
    """GitHub OAuth2 client. Only usable when github_enabled() is True."""

    def __init__(self):
        if not github_enabled():
            logger.warning(
                "GitHub OAuth is not configured. Set GITHUB_CLIENT_ID and "
                "GITHUB_CLIENT_SECRET in your .env to enable GitHub login."
            )

    def _client(self):
        from authlib.integrations.httpx_client import AsyncOAuth2Client
        return AsyncOAuth2Client(
            client_id=settings.GITHUB_CLIENT_ID,
            client_secret=settings.GITHUB_CLIENT_SECRET,
            redirect_uri=settings.GITHUB_REDIRECT_URI,
        )

    def get_authorization_url(self):
        """Get authorization URL for GitHub login."""
        client = self._client()
        uri, state = client.create_authorization_url(
            "https://github.com/login/oauth/authorize",
            scopes=["user:email"],
        )
        return uri, state

    async def get_access_token(self, code: str):
        """Exchange authorization code for access token."""
        client = self._client()
        token = await client.fetch_token(
            "https://github.com/login/oauth/access_token",
            code=code,
        )
        return token

    async def get_user_info(self, token) -> dict:
        """Get user info from GitHub."""
        client = self._client()
        async with client as c:
            resp = await c.get(
                "https://api.github.com/user",
                token=token,
                headers={"Accept": "application/vnd.github.v3+json"},
            )
            user = resp.json()

            # Fetch primary email if not public
            if not user.get("email"):
                resp = await c.get(
                    "https://api.github.com/user/emails",
                    token=token,
                )
                emails = resp.json()
                primary = next((e for e in emails if e.get("primary")), None)
                if primary:
                    user["email"] = primary["email"]

        return user


google_oauth = GoogleOAuth()
github_oauth = GitHubOAuth()
