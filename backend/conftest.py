"""Root-level pytest configuration for the backend package.

Sets asyncio mode to "auto" so all async test functions are handled by
pytest-asyncio without needing the @pytest.mark.asyncio decorator on each one.
"""

import pytest


def pytest_configure(config):
    config.addinivalue_line(
        "markers", "asyncio: mark test as async"
    )
