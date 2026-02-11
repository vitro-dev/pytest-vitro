"""Log wrapper module."""

from __future__ import annotations

import logging
import os


class TestLogger:  # pylint: disable=too-few-public-methods
    """Log wrapper to log test steps from tests."""

    __test__ = False  # Fix PytestCollectionWarning

    def __init__(self) -> None:
        """Initialize log wrapper."""
        self._logger = logging.getLogger("test-logger")

    def log_step(self, message: str) -> None:
        """Log test step.

        :param message: Log message
        """
        _current_test = os.environ.get("PYTEST_CURRENT_TEST")
        if _current_test is None:
            msg = "PYTEST_CURRENT_TEST environment variable is not set."
            raise RuntimeError(msg)
        testname = (_current_test.split(" (setup)")[0]).split("::")[1].replace(" ", "_")
        self._logger.info("[*****LOGGING-STEP*****][%s][%s]", testname, message)
