import jwt
from fastapi import Header, HTTPException
from config import settings

# Supabase signs JWTs with this project's JWT secret (HS256).
# Find it in: Supabase Dashboard -> Project Settings -> API -> JWT Settings -> JWT Secret
# Add it to your .env as SUPABASE_JWT_SECRET

async def get_current_user(authorization: str = Header(...)) -> str:
    """
    FastAPI dependency: verifies the Authorization: Bearer <token> header
    against Supabase's JWT secret, returns the real user_id (the 'sub' claim).

    Use like:
        @router.post("/governance/check")
        async def check(request: GovernanceRequest, user_id: str = Depends(get_current_user)):
            ...
    """
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or malformed Authorization header")

    token = authorization.split(" ", 1)[1]

    try:
        payload = jwt.decode(
            token,
            settings.SUPABASE_JWT_SECRET,
            algorithms=["HS256"],
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