import os
from pathlib import Path

from backend.app.core.config import Settings


def test_pytest_environment_uses_offline_services_and_temporary_sqlite() -> None:
    settings = Settings(_env_file=None)
    database_path = Path(
        settings.database_url.removeprefix("sqlite+aiosqlite:///")
    )

    assert settings.demo_mode is True
    assert settings.environment == "test"
    assert settings.llm_provider == "fake"
    assert settings.llm_api_key is None
    assert settings.embedding_provider == "fake"
    assert settings.vector_store == "memory"
    assert settings.use_fake_redis is True
    assert settings.checkpoint_db_path == ":memory:"
    assert database_path.parent.is_dir()
    assert os.environ["DATABASE_URL"] == settings.database_url
