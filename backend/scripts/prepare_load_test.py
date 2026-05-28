import asyncio
import os
import sys
from pathlib import Path

# Add backend to path
BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(BACKEND_ROOT.parent) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT.parent))

from sqlalchemy import select
from backend.app.db.session import async_session_factory
from backend.app.models.knowledge_base import KnowledgeBase
from backend.app.core.security import create_access_token

async def setup_load_test():
    print("--- DB Status ---")
    async with async_session_factory() as db:
        res = await db.execute(select(KnowledgeBase.id, KnowledgeBase.name))
        kbs = res.all()
        for r in kbs:
            print(f"KB ID: {r[0]}, Name: {r[1]}")
    
    kb_ids = ",".join(str(r[0]) for r in kbs)
    
    print("\n--- Auth Token ---")
    token = create_access_token({"sub": "1"}) # User ID 1
    print(f"JWT_TOKEN: {token}")
    
    print("\n--- Suggested Command ---")
    print(f"export LOCUST_TOKEN={token}")
    print(f"export LOCUST_KB_IDS={kb_ids}")
    print(f"cd backend && uv run locust -f scripts/load_test/locustfile.py --host=http://localhost:8080 --headless -u 10 -r 2 -t 1m")

if __name__ == "__main__":
    asyncio.run(setup_load_test())
