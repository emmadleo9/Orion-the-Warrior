import pytest


def pytest_collection_modifyitems(items):
    for item in items:
        if item.name.startswith("test_telegram_"):
            item.add_marker(pytest.mark.skip(reason="Telegram integration was removed"))
