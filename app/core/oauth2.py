from authlib.integrations.httpx_client import AsyncOAuth2Client
from authlib.oauth2.client import OAuth2Token
from app.config import settings


class GoogleOAuth:
    """Google OAuth2 client."""

    def __init__(self):
        self.client = AsyncOAuth2Client(
            client_id=settings.GOOGLE_CLIENT_ID,
            client_secret=settings.GOOGLE_CLIENT_SECRET,
            redirect_uri=settings.GOOGLE_REDIRECT_URI
        )

    def get_authorization_url(self):
        """Get authorization URL for Google login."""
        uri, state = self.client.create_authorization_url(
            "https://accounts.google.com/o/oauth2/v2/auth",
            scopes=["openid", "email", "profile"]
        )
        return uri, state

    async def get_access_token(self, code: str, state: str) -> OAuth2Token:
        """Exchange authorization code for access token."""
        token = await self.client.fetch_token(
            "https://oauth2.googleapis.com/token",
            code=code
        )
        return token

    async def get_user_info(self, token: OAuth2Token) -> dict:
        """Get user info from Google."""
        async with self.client as client:
            resp = await client.get(
                "https://openidconnect.googleapis.com/v1/userinfo",
                token=token
            )
            return resp.json()


class GitHubOAuth:
    """GitHub OAuth2 client."""

    def __init__(self):
        self.client = AsyncOAuth2Client(
            client_id=settings.GITHUB_CLIENT_ID,
            client_secret=settings.GITHUB_CLIENT_SECRET,
            redirect_uri=settings.GITHUB_REDIRECT_URI
        )

    def get_authorization_url(self):
        """Get authorization URL for GitHub login."""
        uri, state = self.client.create_authorization_url(
            "https://github.com/login/oauth/authorize",
            scopes=["user:email"]
        )
        return uri, state

    async def get_access_token(self, code: str) -> OAuth2Token:
        """Exchange authorization code for access token."""
        token = await self.client.fetch_token(
            "https://github.com/login/oauth/access_token",
            code=code
        )
        return token

    async def get_user_info(self, token: OAuth2Token) -> dict:
        """Get user info from GitHub."""
        async with self.client as client:
            resp = await client.get(
                "https://api.github.com/user",
                token=token,
                headers={"Accept": "application/vnd.github.v3+json"}
            )
            user = resp.json()

            # Get email if not public
            if not user.get("email"):
                resp = await client.get(
                    "https://api.github.com/user/emails",
                    token=token
                )
                emails = resp.json()
                primary = next((e for e in emails if e.get("primary")), None)
                if primary:
                    user["email"] = primary["email"]

            return user


google_oauth = GoogleOAuth()
github_oauth = GitHubOAuth()
