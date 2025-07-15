import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio

async def test_home_route(client: AsyncClient):
    """Tests the home route to ensure the app is alive."""
    response = await client.get("/")
    assert response.status_code == 200
    assert response.text == "Bot is alive ✅" 