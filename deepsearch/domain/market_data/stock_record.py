"""Domain model for stock list records."""

from __future__ import annotations

import re
from dataclasses import dataclass, field, replace
from typing import Any, Iterable, Mapping, Sequence

_BOARD_SPLIT_PATTERN = re.compile(r"[;,/|]+")
DEFAULT_BOARD_FIELDS: tuple[str, ...] = ("board", "board_name", "LISTPLATE_NAME")


def _normalize_symbol(symbol: str | None) -> str:
    if not symbol:
        return ""
    return str(symbol).upper().strip()


def _normalize_optional_string(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    return str(value).strip() or None


def _normalize_iterable(values: Iterable[str]) -> tuple[str, ...]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        normalized = value.strip()
        if not normalized:
            continue
        if normalized not in seen:
            seen.add(normalized)
            ordered.append(normalized)
    return tuple(ordered)


def _merge_board_values(payload: Mapping[str, Any], board_fields: Sequence[str]) -> tuple[str, ...]:
    candidates: list[str] = []
    for field_name in board_fields:
        raw_value = payload.get(field_name)
        if raw_value is None:
            continue
        if isinstance(raw_value, str):
            chunks = _BOARD_SPLIT_PATTERN.split(raw_value) if raw_value else [raw_value]
            candidates.extend(str(chunk) for chunk in chunks)
        elif isinstance(raw_value, Sequence):
            for item in raw_value:
                if item is None:
                    continue
                candidates.append(str(item))
        else:
            candidates.append(str(raw_value))
    return _normalize_iterable(candidates)


@dataclass(slots=True)
class StockListRecord:
    """Immutable representation of a single stock entry within the domain."""

    symbol: str
    name: str
    exchange: str | None = None
    market: str | None = None
    security_type: str | None = None
    status: str | None = None
    boards: tuple[str, ...] = field(default_factory=tuple)
    tags: tuple[str, ...] = field(default_factory=tuple)
    list_date: str | None = None
    delist_date: str | None = None
    company_id: str | None = None
    pinyin: str | None = None
    english_name: str | None = None
    short_name: str | None = None
    is_listed: int | None = None

    def __post_init__(self) -> None:
        self.symbol = _normalize_symbol(self.symbol)
        self.name = self.name.strip() if isinstance(self.name, str) else str(self.name)
        if not self.name:
            self.name = self.symbol
        self.exchange = _normalize_optional_string(self.exchange)
        self.market = _normalize_optional_string(self.market)
        self.security_type = _normalize_optional_string(self.security_type)
        self.status = _normalize_optional_string(self.status)
        self.list_date = _normalize_optional_string(self.list_date)
        self.delist_date = _normalize_optional_string(self.delist_date)
        self.boards = _normalize_iterable(self.boards)
        self.tags = _normalize_iterable(self.tags)
        self.company_id = _normalize_optional_string(self.company_id)
        self.pinyin = _normalize_optional_string(self.pinyin)
        self.english_name = _normalize_optional_string(self.english_name)
        self.short_name = _normalize_optional_string(self.short_name)
        if isinstance(self.is_listed, bool):
            self.is_listed = int(self.is_listed)
        elif isinstance(self.is_listed, (int, float)):
            self.is_listed = int(self.is_listed)
        elif isinstance(self.is_listed, str):
            cleaned = self.is_listed.strip()
            if cleaned:
                try:
                    self.is_listed = int(float(cleaned))
                except ValueError:
                    self.is_listed = None
            else:
                self.is_listed = None
        else:
            self.is_listed = None

    @classmethod
    def from_payload(
        cls,
        payload: Mapping[str, Any],
        *,
        board_fields: Sequence[str] = DEFAULT_BOARD_FIELDS,
    ) -> "StockListRecord":
        symbol = (
            payload.get("symbol")
            or payload.get("code")
            or payload.get("SECURITY_ID")
            or payload.get("SECURITY_CODE")
            or payload.get("MARKET_CODE")
        )
        name = (
            payload.get("name")
            or payload.get("sec_name")
            or payload.get("SECURITY_NAME")
            or payload.get("SEC_NAME_A")
            or symbol
            or ""
        )
        exchange = payload.get("exchange")
        market = payload.get("market")
        security_type = payload.get("security_type") or payload.get("SECURITY_TYPE")
        status = payload.get("status")
        list_date = payload.get("list_date") or payload.get("LIST_DATE")
        delist_date = payload.get("delist_date") or payload.get("DELIST_DATE")
        boards = _merge_board_values(payload, board_fields)

        raw_tags = payload.get("tags")
        tags: tuple[str, ...]
        if isinstance(raw_tags, (list, tuple)):
            tags = _normalize_iterable(str(tag) for tag in raw_tags)
        elif isinstance(raw_tags, str):
            tags = _normalize_iterable(chunk for chunk in _BOARD_SPLIT_PATTERN.split(raw_tags))
        else:
            tags = ()

        company_id = payload.get("company_id") or payload.get("COMPANY_ID")
        pinyin = payload.get("pinyin")
        english_name = payload.get("english_name")
        short_name = payload.get("short_name")
        is_listed = payload.get("is_listed")

        return cls(
            symbol=str(symbol or ""),
            name=str(name or ""),
            exchange=exchange if exchange is None else str(exchange),
            market=market if market is None else str(market),
            security_type=security_type if security_type is None else str(security_type),
            status=status if status is None else str(status),
            boards=boards,
            tags=tags,
            list_date=list_date if list_date is None else str(list_date),
            delist_date=delist_date if delist_date is None else str(delist_date),
            company_id=company_id if company_id is None else str(company_id),
            pinyin=pinyin,
            english_name=english_name,
            short_name=short_name,
            is_listed=is_listed,
        )

    def with_boards(self, boards: Iterable[str]) -> "StockListRecord":
        merged = _normalize_iterable((*self.boards, *boards))
        if merged == self.boards:
            return self
        return replace(self, boards=merged)

    def with_board(self, board: str | None) -> "StockListRecord":
        if not board:
            return self
        return self.with_boards((board,))

    def without_board(self, board: str) -> "StockListRecord":
        if board not in self.boards:
            return self
        remaining = tuple(item for item in self.boards if item != board)
        return replace(self, boards=remaining)

    def with_tag(self, tag: str | None) -> "StockListRecord":
        if not tag:
            return self
        normalized = tag.strip()
        if not normalized or normalized in self.tags:
            return self
        return replace(self, tags=self.tags + (normalized,))

    def without_tag(self, tag: str) -> "StockListRecord":
        if tag not in self.tags:
            return self
        remaining = tuple(item for item in self.tags if item != tag)
        return replace(self, tags=remaining)

    def board_candidates(self) -> tuple[str, ...]:
        """Return raw board names discovered on the record."""
        return self.boards

    def as_mapping(self) -> Mapping[str, Any]:
        """Return a serializable mapping representing the record."""
        return {
            "symbol": self.symbol,
            "name": self.name,
            "exchange": self.exchange,
            "market": self.market,
            "security_type": self.security_type,
            "status": self.status,
            "boards": list(self.boards),
            "tags": list(self.tags),
            "list_date": self.list_date,
            "delist_date": self.delist_date,
            "company_id": self.company_id,
            "pinyin": self.pinyin,
            "english_name": self.english_name,
            "short_name": self.short_name,
            "is_listed": self.is_listed,
        }


__all__ = ["StockListRecord", "DEFAULT_BOARD_FIELDS"]
