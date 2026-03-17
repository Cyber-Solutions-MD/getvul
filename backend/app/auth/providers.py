"""OIDC provider implementations for Google Workspace and Azure Entra ID."""

from __future__ import annotations

import httpx

from app.config import settings


class OIDCTokens:
    """Parsed tokens from an OIDC provider."""

    def __init__(self, id_token: str, access_token: str, refresh_token: str | None = None):
        self.id_token = id_token
        self.access_token = access_token
        self.refresh_token = refresh_token


class OIDCUserInfo:
    """Normalized user info from any OIDC provider."""

    def __init__(
        self,
        subject: str,
        email: str,
        name: str | None = None,
        picture: str | None = None,
        email_verified: bool = False,
        raw: dict | None = None,
    ):
        self.subject = subject
        self.email = email
        self.name = name
        self.picture = picture
        self.email_verified = email_verified
        self.raw = raw or {}


class BaseOIDCProvider:
    """Base class for OIDC providers."""

    authorization_url: str
    token_url: str
    userinfo_url: str
    client_id: str
    client_secret: str
    redirect_uri: str
    scopes: list[str]

    def get_authorization_url(self, state: str) -> str:
        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
            "scope": " ".join(self.scopes),
            "state": state,
            "access_type": "offline",
            "prompt": "consent",
        }
        query = "&".join(f"{k}={httpx.QueryParams({k: v})}" for k, v in params.items())
        # Use httpx to build clean query string
        return f"{self.authorization_url}?{httpx.QueryParams(params)}"

    async def exchange_code(self, code: str) -> OIDCTokens:
        """Exchange authorization code for tokens."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.token_url,
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": self.redirect_uri,
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            response.raise_for_status()
            data = response.json()

        return OIDCTokens(
            id_token=data["id_token"],
            access_token=data["access_token"],
            refresh_token=data.get("refresh_token"),
        )

    async def get_userinfo(self, access_token: str) -> OIDCUserInfo:
        """Fetch user info from the provider's userinfo endpoint."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                self.userinfo_url,
                headers={"Authorization": f"Bearer {access_token}"},
            )
            response.raise_for_status()
            data = response.json()

        return self._parse_userinfo(data)

    def _parse_userinfo(self, data: dict) -> OIDCUserInfo:
        raise NotImplementedError


class GoogleOIDCProvider(BaseOIDCProvider):
    """Google Workspace OIDC provider."""

    authorization_url = "https://accounts.google.com/o/oauth2/v2/auth"
    token_url = "https://oauth2.googleapis.com/token"
    userinfo_url = "https://openidconnect.googleapis.com/v1/userinfo"
    scopes = ["openid", "email", "profile"]

    def __init__(self):
        self.client_id = settings.google_client_id
        self.client_secret = settings.google_client_secret
        self.redirect_uri = settings.google_redirect_uri

    def _parse_userinfo(self, data: dict) -> OIDCUserInfo:
        return OIDCUserInfo(
            subject=data["sub"],
            email=data["email"],
            name=data.get("name"),
            picture=data.get("picture"),
            email_verified=data.get("email_verified", False),
            raw=data,
        )


class AzureOIDCProvider(BaseOIDCProvider):
    """Azure Entra ID OIDC provider."""

    userinfo_url = "https://graph.microsoft.com/oidc/userinfo"
    scopes = ["openid", "email", "profile", "User.Read"]

    def __init__(self, azure_tenant_id: str = "common"):
        self.azure_tenant_id = azure_tenant_id
        self.authorization_url = f"https://login.microsoftonline.com/{azure_tenant_id}/oauth2/v2.0/authorize"
        self.token_url = f"https://login.microsoftonline.com/{azure_tenant_id}/oauth2/v2.0/token"
        self.client_id = settings.azure_client_id
        self.client_secret = settings.azure_client_secret
        self.redirect_uri = settings.azure_redirect_uri

    def _parse_userinfo(self, data: dict) -> OIDCUserInfo:
        return OIDCUserInfo(
            subject=data.get("sub", ""),
            email=data.get("email", ""),
            name=data.get("name"),
            picture=None,  # Azure userinfo doesn't return picture
            email_verified=True,  # Azure validates email at tenant level
            raw=data,
        )


def get_provider(provider_name: str, azure_tenant_id: str = "common") -> BaseOIDCProvider:
    """Factory to get the right OIDC provider."""
    if provider_name == "google":
        return GoogleOIDCProvider()
    elif provider_name == "azure":
        return AzureOIDCProvider(azure_tenant_id=azure_tenant_id)
    else:
        raise ValueError(f"Unknown provider: {provider_name}")
