import pytest
from sqlalchemy import create_engine

from app.config import settings
from app.database import Base, SessionLocal
from app import models

if not settings.test_database_url:
    raise RuntimeError(
        "TEST_DATABASE_URL must be configured before running tests"
    )

if settings.test_database_url == settings.database_url:
    raise RuntimeError(
        "Test database must be different from the development database"
    )

test_engine = create_engine(settings.test_database_url)

# Use the test database for application sessions during tests.
SessionLocal.configure(bind=test_engine)


@pytest.fixture(autouse=True)
def reset_test_database():
    """Start every test with a clean database."""
    Base.metadata.drop_all(bind=test_engine)
    Base.metadata.create_all(bind=test_engine)

    yield