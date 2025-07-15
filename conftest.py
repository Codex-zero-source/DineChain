import pytest_asyncio
import asyncio
from httpx import AsyncClient, ASGITransport
from asgiref.wsgi import WsgiToAsgi
from app import app as flask_app
from orders import init_db
import os

# Set a different database for testing
TEST_DB = 'test_orders.db'

# Apply the test database path at the very beginning
os.environ['DATABASE_PATH'] = TEST_DB

@pytest_asyncio.fixture(scope='session')
async def test_app():
    """Fixture to initialize the database and app for testing."""
    await init_db()
    # Wrap the Flask app with WsgiToAsgi to make it ASGI compatible
    app = WsgiToAsgi(flask_app)
    yield app
    # Teardown: remove the test database
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)

@pytest_asyncio.fixture(scope='function')
async def client(test_app):
    """Fixture to create a test client for the app for each test function."""
    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
        yield client 