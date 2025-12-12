"""Board universe utilities for market data domain."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Iterable, Mapping, MutableMapping, Sequence, Union

from .stock_record import StockListRecord, DEFAULT_BOARD_FIELDS

_BOARD_SPLIT_PATTERN = re.compile(r"[;,/|]+")


def _keyword_hit(text: str, lower: str, keyword: str) -> bool:
    if not keyword:
        return False
    if keyword.isascii():
        return keyword.lower() in lower
    return keyword in text


_BOARD_CANONICAL_SPECS: tuple[dict[str, object], ...] = (
    {
        "name": "主板A股",
        "keywords": ("主板A股", "主板（A股）", "主板-A股", "a股主板", "main board a share"),
        "implies": ("主板", "A股"),
    },
    {
        "name": "主板B股",
        "keywords": ("主板B股", "主板（B股）", "主板-B股", "b股主板", "main board b share"),
        "implies": ("主板", "B股"),
    },
    {
        "name": "科创板A股",
        "keywords": ("科创板A股", "科创板（A股）", "科创板-A股"),
        "implies": ("科创板", "A股"),
    },
    {
        "name": "创业板A股",
        "keywords": ("创业板A股", "创业板（A股）", "创业板-A股"),
        "implies": ("创业板", "A股"),
    },
    {
        "name": "港股主板",
        "keywords": ("港股主板", "香港主板", "hkex main board", "hong kong main board"),
        "implies": ("港股",),
    },
    {
        "name": "港股创业板",
        "keywords": ("港股创业板", "香港创业板", "hkex gem", "hong kong gem", "hk gem"),
        "implies": ("港股", "创业板"),
    },
    {
        "name": "新三板精选层",
        "keywords": ("精选层", "select tier"),
        "implies": ("新三板",),
    },
    {
        "name": "新三板创新层",
        "keywords": ("创新层", "innovation tier"),
        "implies": ("新三板",),
    },
    {
        "name": "新三板基础层",
        "keywords": ("基础层", "base tier"),
        "implies": ("新三板",),
    },
    {
        "name": "科创板",
        "keywords": ("科创板", "科创", "kcb", "star market", "sci-tech"),
    },
    {
        "name": "创业板",
        "keywords": ("创业板", "创业", "gem", "growth enterprise"),
    },
    {
        "name": "北交所",
        "keywords": ("北交所", "北证", "北京证券交易所", "beijing stock exchange", "bse"),
    },
    {
        "name": "中小板",
        "keywords": ("中小板", "中小企业板", "sme板", "sme board"),
    },
    {
        "name": "新三板",
        "keywords": ("新三板", "全国股转", "neeq", "股转系统", "全国中小企业股份转让系统"),
    },
    {
        "name": "港股",
        "keywords": ("港股", "香港市场", "hkex", "hong kong stock"),
    },
    {
        "name": "主板",
        "keywords": (
            "主板",
            "沪主板",
            "深主板",
            "上海主板",
            "深圳主板",
            "沪市主板",
            "深市主板",
            "上证主板",
            "深证主板",
            "sse主板",
            "szse主板",
            "sse main board",
            "szse main board",
            "main board",
            "mainboard",
        ),
    },
    {
        "name": "A股",
        "keywords": ("A股", "a-share", "ashare"),
    },
    {
        "name": "B股",
        "keywords": ("B股", "b-share", "bshare"),
    },
)

_MAIN_BOARD_EXCLUDES: tuple[str, ...] = (
    "港股",
    "香港",
    "hk",
    "科创",
    "创业",
    "北交",
    "bse",
    "新三板",
)


def _derive_board_aliases(raw_board: str) -> set[str]:
    board = raw_board.strip()
    if not board:
        return set()

    normalized = (
        board.replace("（", "(")
        .replace("）", ")")
        .replace("【", "[")
        .replace("】", "]")
        .replace("－", "-")
        .replace("—", "-")
    )
    board_lower = normalized.lower()

    aliases: set[str] = {normalized}

    for spec in _BOARD_CANONICAL_SPECS:
        name_obj = spec.get("name")
        if not isinstance(name_obj, str) or not name_obj:
            continue

        raw_keywords = spec.get("keywords")
        if isinstance(raw_keywords, str):
            keywords: tuple[str, ...] = (raw_keywords,)
        elif isinstance(raw_keywords, Sequence):
            keywords = tuple(item for item in raw_keywords if isinstance(item, str) and item)
        else:
            keywords = ()
        if not keywords:
            continue
        if not any(_keyword_hit(normalized, board_lower, keyword) for keyword in keywords):
            continue

        if name_obj == "主板" and any(
                _keyword_hit(normalized, board_lower, forbidden) for forbidden in _MAIN_BOARD_EXCLUDES
        ):
            continue
        aliases.add(name_obj)

        raw_implies = spec.get("implies")
        if isinstance(raw_implies, str):
            implied_names: tuple[str, ...] = (raw_implies,)
        elif isinstance(raw_implies, Sequence):
            implied_names = tuple(item for item in raw_implies if isinstance(item, str) and item)
        else:
            implied_names = ()

        for implied_name in implied_names:
            aliases.add(implied_name)


    # 防止过度补全：若存在“港股创业板”，确保港股/创业板已添加
    if "港股创业板" in aliases:
        aliases.update({"港股", "创业板"})

    if "主板A股" in aliases:
        aliases.update({"主板", "A股"})

    if "主板B股" in aliases:
        aliases.update({"主板", "B股"})

    if "科创板A股" in aliases:
        aliases.update({"科创板", "A股"})

    if "创业板A股" in aliases:
        aliases.update({"创业板", "A股"})

    if any(name in aliases for name in ("新三板精选层", "新三板创新层", "新三板基础层")):
        aliases.add("新三板")

    if "中小板" in aliases:
        aliases.add("主板")

    return aliases


@dataclass(slots=True)
class BoardUniverse:
    """Maintain the mapping between board identifiers and security codes."""

    _boards: MutableMapping[str, tuple[str, ...]] = field(default_factory=dict)

    def update_from_records(
            self,
            records: Iterable[Union[StockListRecord, Mapping[str, object]]],
            *,
            board_fields: Sequence[str] = DEFAULT_BOARD_FIELDS,
    ) -> None:
        """Refresh board membership based on stock list records."""

        resolved_boards: dict[str, set[str]] = {}

        for entry in records:
            if isinstance(entry, StockListRecord):
                record = entry
            elif isinstance(entry, Mapping):
                record = StockListRecord.from_payload(entry, board_fields=board_fields)
            else:
                continue

            symbol = record.symbol
            if not symbol:
                continue

            candidates = record.board_candidates()
            if not candidates:
                continue

            for raw_board in candidates:
                for board in _derive_board_aliases(raw_board):
                    if not board:
                        continue
                    resolved_boards.setdefault(board, set()).add(symbol)

        for board, codes in resolved_boards.items():
            self._boards[board] = tuple(sorted(codes))

    def resolve_codes(self, board: str) -> Sequence[str]:
        """Return codes belonging to the given board."""

        if not board:
            return ()
        return self._boards.get(board, ())

    def boards(self) -> Sequence[str]:
        """Return available board identifiers."""

        return tuple(sorted(self._boards.keys()))

    def load_snapshot(self, snapshot: Mapping[str, Sequence[str]]) -> None:
        """Restore board membership from a cached snapshot."""

        restored: dict[str, tuple[str, ...]] = {}
        for board, codes in snapshot.items():
            if not board:
                continue
            normalized_codes: list[str] = []
            for code in codes:
                if not code:
                    continue
                normalized = str(code).upper().strip()
                if normalized:
                    normalized_codes.append(normalized)
            if normalized_codes:
                restored[str(board)] = tuple(sorted(set(normalized_codes)))
        self._boards = restored

    def snapshot(self) -> dict[str, list[str]]:
        """Return a serializable snapshot of current board mapping."""

        return {board: list(codes) for board, codes in self._boards.items()}
