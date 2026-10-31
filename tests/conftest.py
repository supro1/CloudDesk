from __future__ import annotations

import atexit
import os
import shutil
import tempfile
from pathlib import Path


_test_data_dir = Path(tempfile.mkdtemp(prefix="clouddesk-pytest-"))
atexit.register(shutil.rmtree, _test_data_dir, ignore_errors=True)

os.environ.update(
    {
        "DEMO_MODE": "true",
        "ENVIRONMENT": "test",
        "DATABASE_URL": (
            f"sqlite+aiosqlite:///{(_test_data_dir / 'support.db').as_posix()}"
        ),
        "CHECKPOINT_DB_PATH": ":memory:",
        "REDIS_URL": "",
        "USE_FAKE_REDIS": "true",
        "LLM_PROVIDER": "fake",
        "LLM_API_KEY": "",
        "EMBEDDING_PROVIDER": "fake",
        "VECTOR_STORE": "memory",
        "LANGCHAIN_TRACING_V2": "false",
    }
)
