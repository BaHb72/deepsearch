"""做T回测阻断原因中心映射。"""

from __future__ import annotations

from typing import Final, TypedDict

BLOCKED_REASON_LABELS: Final[dict[str, str]] = {
    "market_untradable": "市场不可交易",
    "t1_no_sellable": "T+1 无可卖底仓",
    "low_limit_block": "跌停附近无法卖出",
    "sell_qty_too_small": "可卖数量不足一手",
    "high_limit_block": "涨停附近无法买入",
    "buy_qty_too_small": "买入资金不足一手",
    "insufficient_cash": "现金不足",
}


class BlockedSummaryItem(TypedDict):
    code: str
    label: str
    count: int


def get_blocked_reason_label(reason_code: str) -> str:
    """获取阻断原因中文标签。"""

    normalized = str(reason_code).strip()
    if not normalized:
        return "未知阻断原因"
    return BLOCKED_REASON_LABELS.get(normalized, f"未知阻断原因({normalized})")


def build_blocked_summary_zh(summary: dict[str, int]) -> dict[str, int]:
    """按中文标签聚合阻断统计。"""

    output: dict[str, int] = {}
    for reason_code, count in summary.items():
        label = get_blocked_reason_label(reason_code)
        output[label] = output.get(label, 0) + int(count)
    return output


def build_blocked_summary_items(summary: dict[str, int]) -> list[BlockedSummaryItem]:
    """构建带 code/label/count 的统一统计列表。"""

    items: list[BlockedSummaryItem] = [
        {
            "code": reason_code,
            "label": get_blocked_reason_label(reason_code),
            "count": int(count),
        }
        for reason_code, count in summary.items()
    ]
    items.sort(key=lambda item: item["count"], reverse=True)
    return items
