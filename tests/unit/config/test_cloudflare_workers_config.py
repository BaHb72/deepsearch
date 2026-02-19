from core.config.models.cloudflare_workers import CloudflareWorkersConfig


def test_cloudflare_workers_accept_auth_key_alias() -> None:
    cfg = CloudflareWorkersConfig.model_validate(
        {
            "url": "demo-worker.workers.dev",
            "auth_key": "legacy-key",
        }
    )

    assert cfg.api_key == "legacy-key"
    assert cfg.auth_key == "legacy-key"
