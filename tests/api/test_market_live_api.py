"""市场实时行情 API 基础连通性测试"""

import pytest


@pytest.mark.parametrize(
    "path",
    [
        "/api/market/live/strength",
        "/api/market/live/order-imbalance",
        "/api/market/live/auction-quality",
    ],
)
def test_market_live_endpoints_registered(test_client, path):
    response = test_client.get(path)
    assert response.status_code != 404, f"Endpoint {path} should be registered"
