"""Subscription state helpers shared by AmazingData providers."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Iterator, Mapping, MutableMapping, Sequence

from .common import SubscriptionCallback


@dataclass
class SubscriptionInfo:
    """Store subscription metadata for a single symbol."""

    data_type: str = "snapshot"
    callbacks: list[SubscriptionCallback] = field(default_factory=list)
    subscription_id: str | None = None

    def add_callback(self, callback: SubscriptionCallback) -> None:
        if callback not in self.callbacks:
            self.callbacks.append(callback)

    def extend_callbacks(self, callbacks: Sequence[SubscriptionCallback]) -> None:
        for callback in callbacks:
            self.add_callback(callback)

    def remove_callback(self, callback: SubscriptionCallback) -> None:
        if callback in self.callbacks:
            self.callbacks.remove(callback)

    def has_callbacks(self) -> bool:
        return bool(self.callbacks)


class SubscriptionRegistry:
    """Light-weight container to manage AmazingData subscription state."""

    def __init__(self) -> None:
        self._entries: dict[str, SubscriptionInfo] = {}

    def add(self, symbols: Iterable[str], callback: SubscriptionCallback, data_type: str) -> None:
        for symbol in symbols:
            info = self._entries.get(symbol)
            if info is None:
                info = SubscriptionInfo(data_type=data_type)
                self._entries[symbol] = info
            else:
                info.data_type = data_type
            info.add_callback(callback)

    def remove(self, symbols: Iterable[str]) -> list[str]:
        removed: list[str] = []
        for symbol in symbols:
            if symbol in self._entries:
                del self._entries[symbol]
                removed.append(symbol)
        return removed

    def drain(self) -> MutableMapping[str, SubscriptionInfo]:
        snapshot = self._entries
        self._entries = {}
        return snapshot

    def restore(self, entries: Mapping[str, SubscriptionInfo]) -> None:
        for symbol, info in entries.items():
            self._entries[symbol] = info

    def get(self, symbol: str) -> SubscriptionInfo | None:
        return self._entries.get(symbol)

    def __len__(self) -> int:
        return len(self._entries)

    def __bool__(self) -> bool:
        return bool(self._entries)

    def items(self) -> Iterator[tuple[str, SubscriptionInfo]]:
        return iter(self._entries.items())

    def snapshot(self) -> Mapping[str, SubscriptionInfo]:
        return dict(self._entries)

    def clear(self) -> None:
        self._entries.clear()


__all__ = ["SubscriptionInfo", "SubscriptionRegistry"]
