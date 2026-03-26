from __future__ import annotations

# Auth is stubbed — Supabase Auth wiring is Task 3.
# get_current_user returns a mock user so Depends(get_current_user) works
# across all endpoints without breaking anything while auth is being built.

async def get_current_user() -> dict:
    """
    Stub: returns a mock user.
    Replace with real Supabase JWT validation when Task 3 (auth) is implemented.
    """
    return {"sub": "mock_user_id", "email": "dev@accruesmart.com"}
