import pytest
from httpx import AsyncClient


class TestHealthEndpoint:
    @pytest.mark.asyncio
    async def test_health_check(self, client: AsyncClient):
        response = await client.get("/api/v1/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "version" in data

    @pytest.mark.asyncio
    async def test_disclaimer(self, client: AsyncClient):
        response = await client.get("/api/v1/disclaimer")
        assert response.status_code == 200
        data = response.json()
        assert "disclaimer" in data
        assert "research use only" in data["disclaimer"].lower()

    @pytest.mark.asyncio
    async def test_openapi_schema(self, client: AsyncClient):
        response = await client.get("/openapi.json")
        assert response.status_code == 200
        schema = response.json()
        assert "paths" in schema
        assert "info" in schema

    @pytest.mark.asyncio
    async def test_dual_use_check(self, client: AsyncClient):
        response = await client.get("/api/v1/check-dual-use?sequence=MVLDGEQG")
        assert response.status_code == 200
        data = response.json()
        assert "is_sensitive" in data
        assert "disclaimer" in data


class TestTargetsEndpoint:
    @pytest.mark.asyncio
    async def test_list_targets_requires_auth(self, client: AsyncClient):
        response = await client.get("/api/v1/targets")
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_target_not_found_requires_auth(self, client: AsyncClient):
        response = await client.get("/api/v1/targets/NONEXISTENT")
        assert response.status_code == 403
