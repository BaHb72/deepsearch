from __future__ import annotations

from core.utils.network import proxy_client as proxy_client_module
from core.utils.network.proxy_client import ProxyClient, get_proxy_client


def _new_client_without_init() -> ProxyClient:
    return ProxyClient.__new__(ProxyClient)


def test_parse_proxy_server_plain_host_port() -> None:
    client = _new_client_without_init()
    proxies = client._parse_proxy_server("127.0.0.1:10808")
    assert proxies == {
        "http": "http://127.0.0.1:10808",
        "https": "http://127.0.0.1:10808",
    }


def test_parse_proxy_server_protocol_mapping() -> None:
    client = _new_client_without_init()
    proxies = client._parse_proxy_server("http=127.0.0.1:10808;https=127.0.0.1:10809")
    assert proxies == {
        "http": "http://127.0.0.1:10808",
        "https": "http://127.0.0.1:10809",
    }


def test_parse_no_proxy_ignores_local_marker() -> None:
    no_proxy = ProxyClient._parse_no_proxy("<local>;localhost;127.0.0.1;intranet.local")
    assert no_proxy == "localhost,127.0.0.1,intranet.local"


def test_load_system_proxies_respects_env(monkeypatch) -> None:
    client = _new_client_without_init()
    monkeypatch.setenv("HTTPS_PROXY", "http://env-proxy:1080")

    hit = {"ie": False, "winhttp": False}

    def _ie(_: ProxyClient) -> dict[str, str]:
        hit["ie"] = True
        return {"http": "http://127.0.0.1:10808"}

    def _winhttp(_: ProxyClient) -> dict[str, str]:
        hit["winhttp"] = True
        return {"http": "http://127.0.0.1:10808"}

    monkeypatch.setattr(ProxyClient, "_load_windows_internet_settings_proxies", _ie)
    monkeypatch.setattr(ProxyClient, "_load_winhttp_proxies", _winhttp)

    assert client._load_system_proxies() == {}
    assert hit == {"ie": False, "winhttp": False}


def test_load_system_proxies_fallback_to_winhttp(monkeypatch) -> None:
    client = _new_client_without_init()
    for env_key in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"):
        monkeypatch.delenv(env_key, raising=False)

    monkeypatch.setattr(proxy_client_module.os, "name", "nt", raising=False)
    monkeypatch.setattr(ProxyClient, "_load_windows_internet_settings_proxies", lambda _self: {})
    monkeypatch.setattr(
        ProxyClient,
        "_load_winhttp_proxies",
        lambda _self: {"http": "http://127.0.0.1:10808", "https": "http://127.0.0.1:10808"},
    )

    assert client._load_system_proxies() == {
        "http": "http://127.0.0.1:10808",
        "https": "http://127.0.0.1:10808",
    }


def test_get_proxy_client_force_refresh_recreates_instance(monkeypatch) -> None:
    class DummyProxyClient:
        created: list[DummyProxyClient] = []

        def __init__(self, worker_url: str | None = None):
            self.worker_url = worker_url
            self.__class__.created.append(self)

        def update_worker_url(self, worker_url: str | None) -> None:
            self.worker_url = worker_url

    monkeypatch.setattr(proxy_client_module, "ProxyClient", DummyProxyClient)
    monkeypatch.setattr(proxy_client_module, "_proxy_client", None)

    client1 = get_proxy_client(worker_url="https://worker-a.example", force_refresh=False)
    client2 = get_proxy_client(worker_url="https://worker-a.example", force_refresh=True)

    assert client1 is not client2
    assert len(DummyProxyClient.created) == 2
