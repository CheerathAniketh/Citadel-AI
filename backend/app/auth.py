import jwt
from fastapi import Header, HTTPException
from jwt import PyJWKClient

# Supabase project's JWKS endpoint — publishes the public keys used to
# verify tokens signed with the newer asymmetric (ES256) signing method.
# No secret needed here; this is Supabase's public key set.
SUPABASE_URL = "https://qxsyscrbnbrzzvctozht.supabase.co"
JWKS_URL = f"{SUPABASE_URL}/auth/v1/.well-known/jwks.json"

# PyJWKClient caches fetched keys internally, so this is safe to reuse
# across requests without re-fetching every time.
_jwk_client = PyJWKClient(JWKS_URL)


async def get_current_user(authorization: str = Header(...)) -> str:
    """
    FastAPI dependency: verifies the Authorization: Bearer <token> header
    against Supabase's public JWKS (ES256), returns the real user_id
    (the 'sub' claim).

    Use like:
        @router.post("/governance/check")
        async def check(request: GovernanceRequest, user_id: str = Depends(get_current_user)):
            ...
    """
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or malformed Authorization header")

    token = authorization.split(" ", 1)[1]

    try:
        signing_key = _jwk_client.get_signing_key_from_jwt(token)
        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=["ES256"],
            audience="authenticated",
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {e}")

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Token missing user id")

    return user_id