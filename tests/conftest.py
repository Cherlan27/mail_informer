import os

import pytest

from mail_informer import db


@pytest.fixture
def conn():
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL is not set")
    c = db.connect(url)
    c.execute("DROP TABLE IF EXISTS notifications, notifier_state, analyses, analyzer_state, messages, sync_state, schema_migrations")
    db.migrate(c)
    yield c
    c.close()
