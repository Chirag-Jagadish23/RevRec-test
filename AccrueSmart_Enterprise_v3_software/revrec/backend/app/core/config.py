from __future__ import annotations

import os
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL: str = os.environ.get("SUPABASE_URL", "")
SUPABASE_ANON_KEY: str = os.environ.get("SUPABASE_ANON_KEY", "")
SUPABASE_SERVICE_ROLE_KEY: str = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")

# Supabase Postgres connection params (avoids URL-encoding issues with special chars in password)
SUPABASE_DB_HOST: str = os.environ.get("SUPABASE_DB_HOST", "")
SUPABASE_DB_PORT: int = int(os.environ.get("SUPABASE_DB_PORT", "6543"))
SUPABASE_DB_USER: str = os.environ.get("SUPABASE_DB_USER", "")
SUPABASE_DB_PASSWORD: str = os.environ.get("SUPABASE_DB_PASSWORD", "")
SUPABASE_DB_NAME: str = os.environ.get("SUPABASE_DB_NAME", "postgres")

OPENAI_API_KEY: str = os.environ.get("OPENAI_API_KEY", "")
