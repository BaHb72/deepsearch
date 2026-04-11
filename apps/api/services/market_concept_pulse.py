"""市场页概念启动事件与优质股评分服务。"""

from __future__ import annotations

from collections import deque
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any, Iterable, Sequence
from zoneinfo import ZoneInfo

_SH_TZ = ZoneInfo("Asia/Shanghai")


def _clamp(value: float, minimum: float = 0.0, maximum: float = 100.0) -> float:
    return max(minimum, min(maximum, value))


def _safe_float(value: object, default: float = 0.0) -> float:
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace(",", "")
    if not text:
        return default
    try:
        return float(text)
    except ValueError:
        return default


def _to_percentile_ranks(values: Sequence[float]) -> list[float]:
    if not values:
        return []
    ordered = sorted(enumerate(values), key=lambda item: item[1])
    total = max(len(values) - 1, 1)
    ranks = [50.0] * len(values)
    if len(values) == 1:
        return [100.0]

    cursor = 0
    while cursor < len(ordered):
        value = ordered[cursor][1]
        group_end = cursor
        while group_end + 1 < len(ordered) and ordered[group_end + 1][1] == value:
            group_end += 1
        average_rank = (cursor + group_end) / 2
        percentile = round((average_rank / total) * 100.0, 2)
        for position in range(cursor, group_end + 1):
            index = ordered[position][0]
            ranks[index] = percentile
        cursor = group_end + 1
    return ranks


def _has_value(value: object) -> bool:
    return value is not None


def _pick_number(payload: dict[str, Any], *keys: str) -> float | None:
    for key in keys:
        if key not in payload:
            continue
        value = payload.get(key)
        if value is None:
            continue
        parsed = _safe_float(value, default=float("nan"))
        if parsed == parsed:
            return parsed
    return None


def _pick_text(payload: dict[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = payload.get(key)
        text = str(value or "").strip()
        if text:
            return text
    return None


def _sort_key_by_date(payload: dict[str, Any]) -> str:
    return (
        _pick_text(
            payload,
            "trade_date",
            "date",
            "Date",
            "REPORTING_PERIOD",
            "REPORT_PERIOD",
            "ANN_DATE",
        )
        or ""
    )


@dataclass(slots=True, frozen=True)
class StrengthBoardPoint:
    board: str
    speed_per_min: float
    amount_total: float
    lead_stock: str | None = None
    lead_change: float | None = None
    data_source: str | None = None


@dataclass(slots=True, frozen=True)
class StrengthSnapshotFrame:
    captured_at: datetime
    boards: tuple[StrengthBoardPoint, ...]


@dataclass(slots=True, frozen=True)
class ActivatedBoard:
    board: str
    activity_score: float
    speed_per_min: float
    amount_total: float
    lead_stock: str | None = None
    lead_change: float | None = None


@dataclass(slots=True, frozen=True)
class ActivationEvent:
    captured_at: datetime
    label: str
    strongest_board: str
    boards: tuple[ActivatedBoard, ...]

    def to_payload(self) -> dict[str, object]:
        return {
            "captured_at": self.captured_at.astimezone(_SH_TZ).isoformat(),
            "label": self.label,
            "strongest_board": self.strongest_board,
            "boards": [asdict(item) for item in self.boards],
        }


@dataclass(slots=True, frozen=True)
class StockCandidateMetrics:
    symbol: str
    name: str
    last_price: float
    change_pct: float
    amount: float
    technical_raw: float
    capital_raw: float
    fundamental_raw: float
    main_net_inflow: float | None = None
    main_net_inflow_pct: float | None = None
    recent_positive_days: int = 0
    return_5d: float | None = None
    return_20d: float | None = None
    above_ma20: bool = False
    roe_like: float | None = None
    profit_margin: float | None = None
    debt_ratio: float | None = None
    technical_coverage: float = 0.0
    capital_coverage: float = 0.0
    fundamental_coverage: float = 0.0


@dataclass(slots=True, frozen=True)
class RankedStockCandidate:
    symbol: str
    name: str
    last_price: float
    change_pct: float
    amount: float
    quality_score: float
    technical_score: float
    capital_score: float
    fundamental_score: float
    main_net_inflow: float | None = None
    main_net_inflow_pct: float | None = None
    recent_positive_days: int = 0
    return_5d: float | None = None
    return_20d: float | None = None
    above_ma20: bool = False
    roe_like: float | None = None
    profit_margin: float | None = None
    debt_ratio: float | None = None
    confidence_score: float = 0.0
    technical_coverage: float = 0.0
    capital_coverage: float = 0.0
    fundamental_coverage: float = 0.0
    selection_reasons: tuple[str, ...] = ()
    risk_flags: tuple[str, ...] = ()

    def to_payload(self) -> dict[str, object]:
        return {
            "symbol": self.symbol,
            "name": self.name,
            "last_price": self.last_price,
            "change_pct": self.change_pct,
            "amount": self.amount,
            "quality_score": self.quality_score,
            "technical_score": self.technical_score,
            "capital_score": self.capital_score,
            "fundamental_score": self.fundamental_score,
            "main_net_inflow": self.main_net_inflow,
            "main_net_inflow_pct": self.main_net_inflow_pct,
            "recent_positive_days": self.recent_positive_days,
            "return_5d": self.return_5d,
            "return_20d": self.return_20d,
            "above_ma20": self.above_ma20,
            "roe_like": self.roe_like,
            "profit_margin": self.profit_margin,
            "debt_ratio": self.debt_ratio,
            "confidence_score": self.confidence_score,
            "technical_coverage": self.technical_coverage,
            "capital_coverage": self.capital_coverage,
            "fundamental_coverage": self.fundamental_coverage,
            "selection_reasons": list(self.selection_reasons),
            "risk_flags": list(self.risk_flags),
        }


class ConceptPulseHistory:
    """按分钟保留概念强度截面，用于恢复当日启动事件。"""

    def __init__(self, *, max_frames: int = 512) -> None:
        self._frames: deque[StrengthSnapshotFrame] = deque(maxlen=max_frames)
        self._trade_day: str | None = None

    def record(self, *, captured_at: datetime, boards: Sequence[StrengthBoardPoint]) -> None:
        trade_day = captured_at.astimezone(_SH_TZ).strftime("%Y-%m-%d")
        if self._trade_day != trade_day:
            self._trade_day = trade_day
            self._frames.clear()
        if not boards:
            return

        minute_key = captured_at.astimezone(_SH_TZ).replace(second=0, microsecond=0)
        frame = StrengthSnapshotFrame(captured_at=minute_key, boards=tuple(boards))
        if self._frames and self._frames[-1].captured_at == minute_key:
            self._frames[-1] = frame
            return
        self._frames.append(frame)

    def frames(self) -> list[StrengthSnapshotFrame]:
        return list(self._frames)


def normalize_strength_points(
    items: Iterable[dict[str, object] | object],
) -> list[StrengthBoardPoint]:
    points: list[StrengthBoardPoint] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        board = str(item.get("board") or "").strip()
        if not board:
            continue
        lead_stock = str(item.get("lead_stock") or "").strip() or None
        data_source = str(item.get("data_source") or "").strip() or None
        lead_change_raw = item.get("lead_change")
        lead_change = None if lead_change_raw is None else _safe_float(lead_change_raw)
        points.append(
            StrengthBoardPoint(
                board=board,
                speed_per_min=_safe_float(item.get("speed_per_min")),
                amount_total=_safe_float(item.get("amount_total")),
                lead_stock=lead_stock,
                lead_change=lead_change,
                data_source=data_source,
            )
        )
    return points


def build_activation_events(
    frames: Sequence[StrengthSnapshotFrame],
    *,
    score_threshold: float = 72.0,
    limit: int = 16,
) -> list[ActivationEvent]:
    previous_scores: dict[str, float] = {}
    events: list[ActivationEvent] = []

    for frame in frames:
        if not frame.boards:
            continue
        speed_values = [abs(item.speed_per_min) for item in frame.boards]
        amount_values = [abs(item.amount_total) for item in frame.boards]
        lead_values = [max(item.lead_change or 0.0, 0.0) for item in frame.boards]
        speed_ranks = _to_percentile_ranks(speed_values)
        amount_ranks = _to_percentile_ranks(amount_values)
        lead_ranks = _to_percentile_ranks(lead_values)

        if not previous_scores:
            for index, point in enumerate(frame.boards):
                previous_scores[point.board] = round(
                    speed_ranks[index] * 0.55
                    + amount_ranks[index] * 0.30
                    + lead_ranks[index] * 0.15,
                    2,
                )
            continue

        activated: list[ActivatedBoard] = []
        for index, point in enumerate(frame.boards):
            activity_score = round(
                speed_ranks[index] * 0.55 + amount_ranks[index] * 0.30 + lead_ranks[index] * 0.15,
                2,
            )
            previous = previous_scores.get(point.board, 0.0)
            if activity_score >= score_threshold and previous < score_threshold:
                activated.append(
                    ActivatedBoard(
                        board=point.board,
                        activity_score=activity_score,
                        speed_per_min=point.speed_per_min,
                        amount_total=point.amount_total,
                        lead_stock=point.lead_stock,
                        lead_change=point.lead_change,
                    )
                )
            previous_scores[point.board] = activity_score

        if not activated:
            continue

        activated.sort(key=lambda item: item.activity_score, reverse=True)
        strongest = activated[0].board
        label = strongest if len(activated) == 1 else f"{strongest} +{len(activated) - 1}"
        events.append(
            ActivationEvent(
                captured_at=frame.captured_at,
                label=label,
                strongest_board=strongest,
                boards=tuple(activated),
            )
        )

    if limit > 0 and len(events) > limit:
        return events[-limit:]
    return events


def build_ranked_stock_candidates(
    candidates: Sequence[StockCandidateMetrics],
) -> list[RankedStockCandidate]:
    if not candidates:
        return []

    technical_scores = _to_percentile_ranks([item.technical_raw for item in candidates])
    capital_scores = _to_percentile_ranks([item.capital_raw for item in candidates])
    fundamental_scores = _to_percentile_ranks([item.fundamental_raw for item in candidates])

    ranked: list[RankedStockCandidate] = []
    for index, item in enumerate(candidates):
        technical_score = round(
            (item.technical_raw * 0.65 + technical_scores[index] * 0.35)
            * (0.55 + item.technical_coverage / 100.0 * 0.45),
            2,
        )
        capital_score = round(
            (item.capital_raw * 0.65 + capital_scores[index] * 0.35)
            * (0.55 + item.capital_coverage / 100.0 * 0.45),
            2,
        )
        fundamental_score = round(
            (item.fundamental_raw * 0.65 + fundamental_scores[index] * 0.35)
            * (0.55 + item.fundamental_coverage / 100.0 * 0.45),
            2,
        )
        base_score = round(
            technical_score * 0.45 + capital_score * 0.35 + fundamental_score * 0.20,
            2,
        )
        confidence_score = build_confidence_score(
            technical_coverage=item.technical_coverage,
            capital_coverage=item.capital_coverage,
            fundamental_coverage=item.fundamental_coverage,
            amount=item.amount,
        )
        risk_penalty = 0.0
        if item.amount < 80_000_000:
            risk_penalty += 8.0
        elif item.amount < 150_000_000:
            risk_penalty += 4.0
        if item.main_net_inflow_pct is not None and item.main_net_inflow_pct < -2.0:
            risk_penalty += 6.0
        if item.return_20d is not None and item.return_20d < 0:
            risk_penalty += 4.0
        if item.debt_ratio is not None and item.debt_ratio >= 0.72:
            risk_penalty += 5.0
        quality_score = round(
            _clamp(base_score * 0.85 + confidence_score * 0.15 - risk_penalty),
            2,
        )
        selection_reasons = build_selection_reasons(
            item=item,
            technical_score=technical_score,
            capital_score=capital_score,
            fundamental_score=fundamental_score,
            confidence_score=confidence_score,
        )
        risk_flags = build_risk_flags(item=item)
        ranked.append(
            RankedStockCandidate(
                symbol=item.symbol,
                name=item.name,
                last_price=item.last_price,
                change_pct=item.change_pct,
                amount=item.amount,
                quality_score=quality_score,
                technical_score=technical_score,
                capital_score=capital_score,
                fundamental_score=fundamental_score,
                main_net_inflow=item.main_net_inflow,
                main_net_inflow_pct=item.main_net_inflow_pct,
                recent_positive_days=item.recent_positive_days,
                return_5d=item.return_5d,
                return_20d=item.return_20d,
                above_ma20=item.above_ma20,
                roe_like=item.roe_like,
                profit_margin=item.profit_margin,
                debt_ratio=item.debt_ratio,
                confidence_score=confidence_score,
                technical_coverage=round(item.technical_coverage, 2),
                capital_coverage=round(item.capital_coverage, 2),
                fundamental_coverage=round(item.fundamental_coverage, 2),
                selection_reasons=selection_reasons,
                risk_flags=risk_flags,
            )
        )

    ranked.sort(key=lambda item: item.quality_score, reverse=True)
    return ranked


def build_technical_raw(
    *,
    change_pct: float,
    return_5d: float | None,
    return_20d: float | None,
    above_ma20: bool,
    range_position: float | None = None,
) -> float:
    intraday = _clamp((change_pct + 3.0) * 12.5)
    short_term = _clamp(((return_5d or 0.0) + 5.0) * 10.0)
    mid_term = _clamp(((return_20d or 0.0) + 8.0) * 5.0)
    ma_bonus = 100.0 if above_ma20 else 35.0
    range_score = _clamp((range_position or 0.5) * 100.0)
    return (
        intraday * 0.35 + short_term * 0.25 + mid_term * 0.20 + ma_bonus * 0.10 + range_score * 0.10
    )


def build_capital_raw(
    *,
    amount: float,
    main_net_inflow: float | None,
    main_net_inflow_pct: float | None,
    recent_positive_days: int,
) -> float:
    amount_score = _clamp(amount / 300_000_000.0 * 100.0)
    inflow_score = _clamp(((main_net_inflow_pct or 0.0) + 5.0) * 10.0)
    net_score = _clamp(((main_net_inflow or 0.0) / 50_000_000.0) * 100.0)
    positive_days_score = _clamp((recent_positive_days / 5.0) * 100.0)
    return amount_score * 0.20 + inflow_score * 0.40 + net_score * 0.25 + positive_days_score * 0.15


def build_fundamental_raw(
    *,
    roe_like: float | None,
    profit_margin: float | None,
    debt_ratio: float | None,
) -> float:
    roe_score = _clamp((roe_like or 0.0) * 5.0)
    margin_score = _clamp((profit_margin or 0.0) * 6.0)
    debt_penalty_score = 100.0 - _clamp((debt_ratio or 1.0) * 100.0)
    return roe_score * 0.45 + margin_score * 0.35 + debt_penalty_score * 0.20


def build_technical_coverage(
    *,
    return_5d: float | None,
    return_20d: float | None,
    range_position: float | None,
) -> float:
    score = 0.0
    if _has_value(return_5d):
        score += 35.0
    if _has_value(return_20d):
        score += 35.0
    if _has_value(range_position):
        score += 30.0
    return round(score, 2)


def build_capital_coverage(
    *,
    main_net_inflow: float | None,
    main_net_inflow_pct: float | None,
    has_rows: bool,
) -> float:
    score = 0.0
    if has_rows:
        score += 25.0
    if _has_value(main_net_inflow):
        score += 40.0
    if _has_value(main_net_inflow_pct):
        score += 35.0
    return round(score, 2)


def build_fundamental_coverage(
    *,
    roe_like: float | None,
    profit_margin: float | None,
    debt_ratio: float | None,
) -> float:
    score = 0.0
    if _has_value(roe_like):
        score += 35.0
    if _has_value(profit_margin):
        score += 35.0
    if _has_value(debt_ratio):
        score += 30.0
    return round(score, 2)


def build_confidence_score(
    *,
    technical_coverage: float,
    capital_coverage: float,
    fundamental_coverage: float,
    amount: float,
) -> float:
    completeness_score = (
        technical_coverage * 0.45 + capital_coverage * 0.35 + fundamental_coverage * 0.20
    )
    liquidity_score = _clamp(amount / 200_000_000.0 * 100.0)
    return round(_clamp(completeness_score * 0.85 + liquidity_score * 0.15), 2)


def build_selection_reasons(
    *,
    item: StockCandidateMetrics,
    technical_score: float,
    capital_score: float,
    fundamental_score: float,
    confidence_score: float,
) -> tuple[str, ...]:
    reasons: list[str] = []

    if technical_score >= 70.0:
        if item.above_ma20 and (item.return_20d or 0.0) >= 0:
            reasons.append("技术面居前，价格运行在 MA20 上方")
        elif (item.return_5d or 0.0) >= 8.0:
            reasons.append("短线动能明显强于同概念候选")
        else:
            reasons.append("技术面评分位于当前概念前列")

    if capital_score >= 70.0:
        if (item.main_net_inflow_pct or 0.0) > 0 and item.recent_positive_days >= 3:
            reasons.append(f"近5日主力资金 {item.recent_positive_days} 日净流入")
        elif (item.main_net_inflow_pct or 0.0) > 0:
            reasons.append("主力净流入强于同概念候选")
        elif item.amount >= 300_000_000:
            reasons.append("成交承接充足，板块启动时更容易获得跟随资金")

    if fundamental_score >= 70.0:
        if (item.roe_like or 0.0) >= 10.0 and (item.profit_margin or 0.0) >= 8.0:
            reasons.append("盈利质量较好，基本面支持度更强")
        elif item.debt_ratio is not None and item.debt_ratio <= 0.55:
            reasons.append("资产负债结构稳健，基本面风险相对可控")
        else:
            reasons.append("基本面评分位于当前概念前列")

    if confidence_score >= 80.0:
        reasons.append("数据覆盖较完整，当前判断可靠性更高")

    if not reasons:
        reasons.append("综合评分在当前概念候选中居前")

    unique_reasons: list[str] = []
    for reason in reasons:
        if reason and reason not in unique_reasons:
            unique_reasons.append(reason)
        if len(unique_reasons) >= 3:
            break
    return tuple(unique_reasons)


def build_risk_flags(*, item: StockCandidateMetrics) -> tuple[str, ...]:
    risks: list[str] = []

    if item.technical_coverage < 60.0:
        risks.append("技术面样本不足")
    if item.capital_coverage < 60.0:
        risks.append("资金流数据覆盖不足")
    if item.fundamental_coverage < 60.0:
        risks.append("基本面覆盖不足")
    if item.amount < 80_000_000:
        risks.append("成交额偏低")
    if item.technical_coverage >= 40.0 and not item.above_ma20:
        risks.append("股价仍在 MA20 下方")
    if item.main_net_inflow_pct is not None and item.main_net_inflow_pct < 0:
        risks.append("主力资金当日转弱")
    if item.return_20d is not None and item.return_20d < 0:
        risks.append("20日趋势仍偏弱")
    if item.debt_ratio is not None and item.debt_ratio >= 0.7:
        risks.append("资产负债率偏高")

    unique_risks: list[str] = []
    for risk in risks:
        if risk and risk not in unique_risks:
            unique_risks.append(risk)
        if len(unique_risks) >= 3:
            break
    return tuple(unique_risks)


def group_rows_by_symbol(
    rows: Iterable[dict[str, Any]],
    *keys: str,
) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        symbol = _pick_text(row, *keys)
        if not symbol:
            continue
        grouped.setdefault(symbol.upper(), []).append(row)
    for values in grouped.values():
        values.sort(key=_sort_key_by_date, reverse=True)
    return grouped


def extract_capital_metrics(rows: Sequence[dict[str, Any]]) -> dict[str, float | int | None]:
    if not rows:
        return {
            "main_net_inflow": None,
            "main_net_inflow_pct": None,
            "recent_positive_days": 0,
        }

    latest = max(rows, key=_sort_key_by_date)
    recent_rows = sorted(rows, key=_sort_key_by_date, reverse=True)[:5]
    positive_days = 0
    main_net_inflow: float | None = None
    main_net_inflow_pct: float | None = None

    main_net_inflow = _pick_number(
        latest,
        "main_net_inflow",
        "main_net_amount",
        "net_inflow",
    )
    if main_net_inflow is None:
        large_inflow = _pick_number(latest, "large_inflow", "largeInflow") or 0.0
        large_outflow = _pick_number(latest, "large_outflow", "largeOutflow") or 0.0
        medium_inflow = _pick_number(latest, "medium_inflow", "mediumInflow") or 0.0
        medium_outflow = _pick_number(latest, "medium_outflow", "mediumOutflow") or 0.0
        small_inflow = _pick_number(latest, "small_inflow", "smallInflow") or 0.0
        small_outflow = _pick_number(latest, "small_outflow", "smallOutflow") or 0.0
        computed = (large_inflow - large_outflow) + (medium_inflow - medium_outflow)
        if computed or (small_inflow - small_outflow):
            main_net_inflow = computed
            total_flow = (
                large_inflow
                + large_outflow
                + medium_inflow
                + medium_outflow
                + small_inflow
                + small_outflow
            )
            if total_flow > 0:
                main_net_inflow_pct = round(computed / total_flow * 100.0, 2)

    if main_net_inflow_pct is None:
        main_net_inflow_pct = _pick_number(
            latest,
            "main_net_inflow_pct",
            "main_net_pct",
            "net_inflow_pct",
        )

    for row in recent_rows:
        row_inflow = _pick_number(
            row,
            "main_net_inflow",
            "main_net_amount",
            "net_inflow",
        )
        if row_inflow is None:
            large_inflow = _pick_number(row, "large_inflow", "largeInflow") or 0.0
            large_outflow = _pick_number(row, "large_outflow", "largeOutflow") or 0.0
            medium_inflow = _pick_number(row, "medium_inflow", "mediumInflow") or 0.0
            medium_outflow = _pick_number(row, "medium_outflow", "mediumOutflow") or 0.0
            row_inflow = (large_inflow - large_outflow) + (medium_inflow - medium_outflow)
        if (row_inflow or 0.0) > 0:
            positive_days += 1

    return {
        "main_net_inflow": main_net_inflow,
        "main_net_inflow_pct": main_net_inflow_pct,
        "recent_positive_days": positive_days,
    }


def extract_technical_metrics(
    *,
    current_price: float,
    current_change_pct: float,
    kline_rows: Sequence[dict[str, Any]],
) -> dict[str, float | bool | None]:
    if not kline_rows or current_price <= 0:
        return {
            "return_5d": None,
            "return_20d": None,
            "above_ma20": False,
            "range_position": None,
        }

    sorted_rows = sorted(kline_rows, key=_sort_key_by_date, reverse=True)
    closes = [_pick_number(row, "close", "last", "price") for row in sorted_rows]
    closes = [item for item in closes if item is not None and item > 0]
    if not closes:
        return {
            "return_5d": None,
            "return_20d": None,
            "above_ma20": False,
            "range_position": None,
        }

    return_5d: float | None = None
    return_20d: float | None = None
    if len(closes) >= 5 and closes[4] > 0:
        return_5d = round((current_price / closes[4] - 1.0) * 100.0, 2)
    if len(closes) >= 20 and closes[19] > 0:
        return_20d = round((current_price / closes[19] - 1.0) * 100.0, 2)

    ma20_window = closes[:20] if len(closes) >= 20 else closes
    ma20 = sum(ma20_window) / len(ma20_window)
    above_ma20 = bool(ma20 and current_price >= ma20)

    range_window = closes[:20] if len(closes) >= 20 else closes
    high_20 = max(range_window)
    low_20 = min(range_window)
    range_position = 0.5
    if high_20 > low_20:
        range_position = (current_price - low_20) / (high_20 - low_20)

    return {
        "return_5d": return_5d,
        "return_20d": return_20d,
        "above_ma20": above_ma20,
        "range_position": round(_clamp(range_position, 0.0, 1.0), 4),
        "change_pct": current_change_pct,
    }


def extract_fundamental_metrics(
    *,
    income_rows: Sequence[dict[str, Any]],
    balance_rows: Sequence[dict[str, Any]],
) -> dict[str, float | None]:
    latest_income = max(income_rows, key=_sort_key_by_date) if income_rows else {}
    latest_balance = max(balance_rows, key=_sort_key_by_date) if balance_rows else {}

    revenue = _pick_number(
        latest_income,
        "TOT_OPERA_REV",
        "OPERA_REV",
        "revenue",
        "operating_revenue",
    )
    net_profit = _pick_number(
        latest_income,
        "NET_PRO_EXCL_MIN_INT_INC",
        "NET_PRO_INCL_MIN_INT_INC",
        "NET_PROFIT",
        "net_profit",
    )
    equity = _pick_number(
        latest_balance,
        "TOT_SHARE_EQUITY_EXCL_MIN_INT",
        "TOT_SHARE_EQUITY_INCL_MIN_INT",
        "shareholder_equity",
        "equity",
    )
    total_assets = _pick_number(
        latest_balance,
        "TOTAL_ASSETS",
        "total_assets",
    )
    total_liab = _pick_number(
        latest_balance,
        "TOTAL_LIAB",
        "total_liability",
        "liabilities",
    )

    roe_like = None
    if equity and equity > 0 and net_profit is not None:
        roe_like = round(net_profit / equity * 100.0, 2)

    profit_margin = None
    if revenue and revenue > 0 and net_profit is not None:
        profit_margin = round(net_profit / revenue * 100.0, 2)

    debt_ratio = None
    if total_assets and total_assets > 0 and total_liab is not None:
        debt_ratio = round(total_liab / total_assets, 4)

    return {
        "roe_like": roe_like,
        "profit_margin": profit_margin,
        "debt_ratio": debt_ratio,
    }
