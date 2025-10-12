from __future__ import annotations

from typing import Any, Protocol


class MockerFixture(Protocol):
    """最小化的 pytest-mock Fixture 协议。"""

    def __call__(self, *args: Any, **kwargs: Any) -> Any: ...

    def patch(self, target: str, **kwargs: Any) -> Any: ...

    def spy(self, obj: Any, name: str) -> Any: ...

    def Mock(self, *args: Any, **kwargs: Any) -> Any: ...


__all__ = ["MockerFixture"]

