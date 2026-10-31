import json
import logging
import os
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from pydantic import SecretStr, ValidationError

from backend.app.core.config import Settings
from backend.app.core.logging import JsonFormatter, setup_logging


class SettingsTests(unittest.TestCase):
    def test_defaults_support_offline_demo(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            settings = Settings(_env_file=None)

        self.assertTrue(settings.demo_mode)
        self.assertEqual(settings.llm_provider, "fake")
        self.assertEqual(settings.embedding_provider, "fake")
        self.assertEqual(settings.vector_store, "memory")
        self.assertEqual(settings.embedding_dimensions, 384)

    def test_environment_overrides_and_parses_cors_origins(self) -> None:
        environment = {
            "DEMO_MODE": "false",
            "CORS_ORIGINS": "http://localhost:3000, https://console.example.com",
            "JWT_SECRET": "test-secret",
            "MAX_REFUND_WITHOUT_APPROVAL": "25.50",
            "VECTOR_STORE": "qdrant",
        }
        with patch.dict(os.environ, environment, clear=True):
            settings = Settings(_env_file=None)

        self.assertFalse(settings.demo_mode)
        self.assertEqual(
            settings.cors_origins,
            ["http://localhost:3000", "https://console.example.com"],
        )
        self.assertIsInstance(settings.jwt_secret, SecretStr)
        self.assertEqual(settings.jwt_secret.get_secret_value(), "test-secret")
        self.assertEqual(settings.effective_jwt_secret, "test-secret")
        self.assertEqual(settings.max_refund_without_approval, Decimal("25.50"))
        self.assertEqual(settings.vector_store, "qdrant")

    def test_invalid_positive_settings_are_rejected(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(ValidationError):
                Settings(embedding_dimensions=0, _env_file=None)

    def test_supabase_secret_takes_precedence(self) -> None:
        settings = Settings(
            jwt_secret="local-secret",
            supabase_jwt_secret="supabase-secret",
            _env_file=None,
        )

        self.assertEqual(settings.effective_jwt_secret, "supabase-secret")

    def test_dotenv_file_is_loaded(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            with tempfile.TemporaryDirectory() as directory:
                env_file = Path(directory) / ".env"
                env_file.write_text(
                    "DEMO_MODE=false\nLLM_PROVIDER=fake\n", encoding="utf-8"
                )

                settings = Settings(_env_file=env_file)

        self.assertFalse(settings.demo_mode)
        self.assertEqual(settings.llm_provider, "fake")

    def test_json_formatter_includes_request_context(self) -> None:
        record = logging.LogRecord(
            name="clouddesk.api",
            level=logging.INFO,
            pathname=__file__,
            lineno=12,
            msg="Request completed",
            args=(),
            exc_info=None,
        )
        record.request_id = "request-123"
        record.workflow_id = "workflow-456"

        payload = json.loads(JsonFormatter().format(record))

        self.assertEqual(payload["level"], "INFO")
        self.assertEqual(payload["message"], "Request completed")
        self.assertEqual(payload["request_id"], "request-123")
        self.assertEqual(payload["workflow_id"], "workflow-456")
        self.assertTrue(payload["timestamp"].endswith("Z"))

    def test_setup_logging_is_idempotent_and_rejects_unknown_levels(self) -> None:
        root_logger = logging.getLogger()
        original_handlers = root_logger.handlers[:]
        original_level = root_logger.level
        try:
            root_logger.handlers.clear()
            setup_logging("DEBUG")
            first_handlers = root_logger.handlers[:]
            setup_logging("INFO")

            self.assertEqual(root_logger.handlers, first_handlers)
            self.assertEqual(root_logger.level, logging.INFO)
            self.assertTrue(
                all(isinstance(handler.formatter, JsonFormatter) for handler in root_logger.handlers)
            )
            with self.assertRaises(ValueError):
                setup_logging("NOT_A_LEVEL")
        finally:
            root_logger.handlers[:] = original_handlers
            root_logger.setLevel(original_level)


if __name__ == "__main__":
    unittest.main()
