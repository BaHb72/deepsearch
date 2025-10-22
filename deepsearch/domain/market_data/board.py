"""Board universe utilities for market data domain."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Iterable, Mapping, MutableMapping, Sequence

_BOARD_SPLIT_PATTERN = re.compile(r"[;,/|]+")


@dataclass(slots=True)
class BoardUniverse:
    """Maintain the mapping between board identifiers and security codes."""

    _boards: MutableMapping[str, tuple[str, ...]] = field(default_factory=dict)

    def update_from_records(
            self,
            records: Iterable[Mapping[str, object]],
            *,
            code_field: str = "symbol",
            board_field: str = "board",
            board_aliases: Sequence[str] | None = None,
    ) -> None:
        """Refresh board membership based on a stock list payload."""

        resolved_boards: dict[str, set[str]] = {}
        aliases = tuple(board_aliases or ("board", "LISTPLATE_NAME", "board_name"))

        for record in records:
            code_raw = record.get(code_field)
            if not code_raw:
                continue
            code = str(code_raw).upper().strip()
            if not code:
                continue

            board_value = None
            for key in (board_field, *aliases):
                value = record.get(key)
                if value:
                    board_value = value
                    break
            if not board_value:
                continue

            if isinstance(board_value, (list, tuple)):
                candidates = [str(item) for item in board_value]
            else:
                candidates = _BOARD_SPLIT_PATTERN.split(str(board_value))

            for raw_board in candidates:
                board = raw_board.strip()
                if not board:
                    continue
                resolved_boards.setdefault(board, set()).add(code)

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
