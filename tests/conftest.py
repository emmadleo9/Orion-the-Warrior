import pytest


def pytest_collection_modifyitems(items):
    # Telegram integration tests are active again; nothing is skipped here.
    return
