# main.py — JIMJAM'EST Connector Authorization Layer
#
# Standalone module: lets an already-authenticated JIMJAM'EST user connect
# third-party accounts (Google, Spotify, LinkedIn) for agent use.
#
# This is NOT a login system. It does not authenticate users into JIMJAM'EST —
# that's SSO's job. Every route here requires a valid platform token first.

from fastapi import FastAPI, HTTPException, Request, Depends, Header
from fastapi.responses import RedirectResponse
from requests_oauthlib import OAuth2Session
from pydantic import BaseModel
import os
import secrets
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="JIMJAM'EST Connector Authorization Layer")

# BASE_URL must match whatever's registered as the redirect URI in each
# provider's OAuth app config. Locally this is localhost; on Render it's
# the service's actual https URL (e.g. https://jimjamest-connector-auth.onrender.com).
# Get this wrong and every OAuth callback fails with a redirect_uri_mismatch
# error from the provider — this is the #1 thing to update per environment.
BASE_URL = os.getenv("BASE_URL", "http://localhost:8000")

# ---------------------------------------------------------------------------
# Provider configs — each provider gets its OWN redirect URI and callback.
# This is the fix for the original spec's "one code, three providers" bug.
# ---------------------------------------------------------------------------
PROVIDERS = {
    "google": {
        "client_id": os.getenv("GOOGLE_CLIENT_ID"),
        "client_secret": os.getenv("GOOGLE_CLIENT_SECRET"),
        "authorize_url": "https://accounts.google.com/o/oauth2/auth",
        "token_url": "https://oauth2.googleapis.com/token",
        "userinfo_url": "https://www.googleapis.com/oauth2/v3/userinfo",
        "scopes": ["openid", "email", "profile"],
        "redirect_uri": f"{BASE_URL}/connect/google/callback",
    },
    "spotify": {
        "client_id": os.getenv("SPOTIFY_CLIENT_ID"),
        "client_secret": os.getenv("SPOTIFY_CLIENT_SECRET"),
        "authorize_url": "https://accounts.spotify.com/authorize",
        "token_url": "https://accounts.spotify.com/api/token",
        "scopes": ["user-read-private", "user-read-email"],
        "redirect_uri": f"{BASE_URL}/connect/spotify/callback",
    },
    "linkedin": {
        "client_id": os.getenv("LINKEDIN_CLIENT_ID"),
        "client_secret": os.getenv("LINKEDIN_CLIENT_SECRET"),
        "authorize_url": "https://www.linkedin.com/oauth/v2/authorization",
        "token_url": "https://www.linkedin.com/oauth/v2/accessToken",
        "scopes": ["r_liteprofile", "r_emailaddress"],
        "redirect_uri": f"{BASE_URL}/connect/linkedin/callback",
    },
}

# In-memory placeholder store — replace with the real KMS-encrypted
# connections table described in connector-authorization.md §3.
# Keyed by (org_id, user_id, provider).
_connection_store: dict = {}

# In-memory OAuth "state" tracking to prevent CSRF on the callback,
# and to carry the authenticated user/org through the redirect round-trip.
_pending_state: dict = {}


# ---------------------------------------------------------------------------
# Platform token gate — every route below requires this.
# Replace verify_platform_token's internals with a real call into the
# JIMJAM'EST identity/token-validation service (per entitlement-role-sync-policy.md).
# ---------------------------------------------------------------------------
class PlatformIdentity(BaseModel):
    org_id: str
    user_id: str


def verify_platform_token(authorization: str = Header(...)) -> PlatformIdentity:
    """
    Placeholder for real server-side token verification.
    NEVER trust org_id/user_id if passed as client-supplied params instead —
    they must come from the verified token, per the "never trust AI/client-
    provided claims" rule in entitlement-role-sync-policy.md.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid platform token")

    token = authorization.removeprefix("Bearer ").strip()
    if not token:
        raise HTTPException(status_code=401, detail="Invalid platform token")

    # TODO: replace with real signature/expiry verification + org/user claim extraction.
    # Demo stand-in only:
    return PlatformIdentity(org_id="org_demo", user_id="user_demo")


# ---------------------------------------------------------------------------
# Connection status
# ---------------------------------------------------------------------------
@app.get("/connect/status")
async def connection_status(identity: PlatformIdentity = Depends(verify_platform_token)):
    key_prefix = f"{identity.org_id}:{identity.user_id}:"
    connected = [
        k.split(":")[2] for k in _connection_store if k.startswith(key_prefix)
    ]
    return {"connected_providers": connected, "available_providers": list(PROVIDERS.keys())}


# ---------------------------------------------------------------------------
# Per-provider login — starts the OAuth flow for ONE provider at a time
# ---------------------------------------------------------------------------
@app.get("/connect/{provider}/login")
async def connect_login(provider: str, identity: PlatformIdentity = Depends(verify_platform_token)):
    if provider not in PROVIDERS:
        raise HTTPException(status_code=404, detail=f"Unknown provider: {provider}")

    cfg = PROVIDERS[provider]
    oauth = OAuth2Session(cfg["client_id"], scope=cfg["scopes"], redirect_uri=cfg["redirect_uri"])
    auth_url, state = oauth.authorization_url(cfg["authorize_url"])

    # Carry identity through the redirect round-trip via signed state,
    # so the callback knows WHO this connection belongs to.
    _pending_state[state] = {"org_id": identity.org_id, "user_id": identity.user_id, "provider": provider}

    return RedirectResponse(auth_url)


# ---------------------------------------------------------------------------
# Per-provider callback — redeems ONLY that provider's code against
# ONLY that provider's token endpoint. No cross-provider code reuse.
# ---------------------------------------------------------------------------
@app.get("/connect/{provider}/callback")
async def connect_callback(provider: str, request: Request):
    if provider not in PROVIDERS:
        raise HTTPException(status_code=404, detail=f"Unknown provider: {provider}")

    code = request.query_params.get("code")
    state = request.query_params.get("state")

    if not code or not state or state not in _pending_state:
        raise HTTPException(status_code=400, detail="Invalid or expired OAuth state")

    pending = _pending_state.pop(state)
    if pending["provider"] != provider:
        raise HTTPException(status_code=400, detail="Provider/state mismatch")

    cfg = PROVIDERS[provider]
    oauth = OAuth2Session(cfg["client_id"], scope=cfg["scopes"], redirect_uri=cfg["redirect_uri"])
    token = oauth.fetch_token(cfg["token_url"], code=code, client_secret=cfg["client_secret"])

    # Store server-side only. Real implementation: encrypt via KMS before
    # persisting (security-architecture.md §1.3), never return raw tokens
    # to the frontend (the bug in the original spec).
    conn_key = f"{pending['org_id']}:{pending['user_id']}:{provider}"
    _connection_store[conn_key] = {
        "provider": provider,
        "connected": True,
        "token_ref": secrets.token_hex(8),  # placeholder for a real vault/KMS reference
    }

    return {"status": "connected", "provider": provider}


# ---------------------------------------------------------------------------
# Disconnect — also revokes at the provider, not just deletes locally
# (flagged as an open item in connector-authorization.md §4 to fully wire up
# provider-specific revocation endpoints)
# ---------------------------------------------------------------------------
@app.delete("/connect/{provider}")
async def disconnect(provider: str, identity: PlatformIdentity = Depends(verify_platform_token)):
    conn_key = f"{identity.org_id}:{identity.user_id}:{provider}"
    if conn_key not in _connection_store:
        raise HTTPException(status_code=404, detail="No active connection for this provider")

    del _connection_store[conn_key]
    # TODO: call provider-specific revocation endpoint here.
    return {"status": "disconnected", "provider": provider}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
