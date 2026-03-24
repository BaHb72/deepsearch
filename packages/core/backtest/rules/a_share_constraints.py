"""A-share backtest order constraints."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AShareOrderConstraintInput:
    """Context used to evaluate A-share order constraints."""

    symbol: str
    side: str
    size: float
    current_price: float
    position_size: float
    intraday_bought_qty: float
    high_limited: float | None = None
    low_limited: float | None = None
    is_suspended: bool = False


def is_a_share_symbol(symbol: str) -> bool:
    """Best-effort A-share stock code detection."""

    normalized = str(symbol).strip().upper().replace("-", "").replace("_", "")
    if not normalized:
        return False

    def _is_stock_code(code_part: str, market: str | None = None) -> bool:
        if not (code_part.isdigit() and len(code_part) == 6):
            return False
        prefix = code_part[:3]
        if market == "SH":
            return prefix in {"600", "601", "603", "605", "688", "689"}
        if market == "SZ":
            return prefix in {"000", "001", "002", "003", "300", "301"}
        if market == "BJ":
            return code_part.startswith(("4", "8"))
        return prefix in {
            "000",
            "001",
            "002",
            "003",
            "300",
            "301",
            "600",
            "601",
            "603",
            "605",
            "688",
            "689",
        } or code_part.startswith(("4", "8"))

    if "." in normalized:
        code_part, market = normalized.split(".", 1)
        return market in {"SH", "SZ", "BJ"} and _is_stock_code(code_part, market)
    if normalized.endswith(("SH", "SZ", "BJ")) and len(normalized) > 2:
        return _is_stock_code(normalized[:-2], normalized[-2:])
    if normalized.startswith(("SH", "SZ", "BJ")) and len(normalized) > 2:
        return _is_stock_code(normalized[2:], normalized[:2])
    return _is_stock_code(normalized)


def evaluate_a_share_order_constraints(context: AShareOrderConstraintInput) -> str | None:
    """Return blocked reason code if the order violates A-share constraints."""

    side = context.side.upper()
    if side not in {"BUY", "SELL"}:
        return None

    if context.current_price <= 0 or context.size <= 0 or context.is_suspended:
        return "market_untradable"

    if side == "BUY":
        if context.high_limited and context.high_limited > 0:
            if context.current_price >= context.high_limited * 0.9999:
                return "high_limit_block"
        return None

    # SELL side constraints:
    sellable_qty = max(context.position_size - context.intraday_bought_qty, 0.0)
    if sellable_qty + 1e-9 < context.size:
        return "t1_no_sellable"
    if context.low_limited and context.low_limited > 0:
        if context.current_price <= context.low_limited * 1.0001:
            return "low_limit_block"
    return None
