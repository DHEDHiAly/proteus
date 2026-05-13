import pytest
import pytest_asyncio
from typing import AsyncGenerator, Generator
from fastapi import FastAPI
from httpx import AsyncClient


@pytest.fixture(scope="session")
def app() -> FastAPI:
    from app.main import app
    return app


@pytest_asyncio.fixture
async def client(app: FastAPI):
    async with AsyncClient(app=app, base_url="http://test") as c:
        yield c


@pytest.fixture
def sample_sequence() -> str:
    return "MVLDGEQG"


@pytest.fixture
def sample_protein_sequence() -> str:
    return "MVLDGEQGMVLDGEQG"


@pytest.fixture
def mcmc_config() -> dict:
    return {
        "mcmc": {
            "num_chains": 2,
            "temperatures": [0.5, 1.0],
            "steps_per_chain": 10,
            "swap_interval": 5,
            "proposal_distribution": "esm_guided",
        },
        "scoring": {
            "binding_weight": 0.5,
            "stability_weight": 0.25,
            "solubility_weight": 0.15,
            "bbb_weight": 0.10,
            "hydrophobicity_penalty": 0.05,
            "charge_penalty": 0.02,
            "aggregation_penalty": 0.08,
        },
        "convergence": {
            "gelman_rubin_threshold": 1.05,
            "min_effective_samples": 10,
            "check_interval": 5,
            "patience": 5,
        },
    }
