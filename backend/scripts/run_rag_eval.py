import asyncio
import json
from pathlib import Path
import sys

BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(BACKEND_ROOT.parent) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT.parent))

from backend.app.db.session import async_session_factory
from backend.app.services.rag_real_chain_eval_service import run_real_chain_eval


DEFAULT_FIXTURE_PATH = (
    BACKEND_ROOT / "tests" / "fixtures" / "rag_eval_cases.json"
)


async def _main() -> None:
    async with async_session_factory() as db:
        summary = await run_real_chain_eval(db, DEFAULT_FIXTURE_PATH)
    print(json.dumps(summary.__dict__, ensure_ascii=False, indent=2, default=lambda value: value.__dict__))


if __name__ == "__main__":
    asyncio.run(_main())
