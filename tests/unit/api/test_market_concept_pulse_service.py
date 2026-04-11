from datetime import datetime

from apps.api.services.market_concept_pulse import (
    StockCandidateMetrics,
    StrengthBoardPoint,
    StrengthSnapshotFrame,
    build_activation_events,
    build_capital_coverage,
    build_fundamental_coverage,
    build_ranked_stock_candidates,
    build_technical_coverage,
    extract_capital_metrics,
)


def test_build_activation_events_skips_first_frame_and_waits_for_threshold_cross():
    frame_a = StrengthSnapshotFrame(
        captured_at=datetime(2026, 4, 10, 9, 35),
        boards=(
            StrengthBoardPoint(
                board="机器人", speed_per_min=10.0, amount_total=200.0, lead_change=4.0
            ),
            StrengthBoardPoint(
                board="AI应用", speed_per_min=1.0, amount_total=20.0, lead_change=0.5
            ),
        ),
    )
    frame_b = StrengthSnapshotFrame(
        captured_at=datetime(2026, 4, 10, 9, 36),
        boards=(
            StrengthBoardPoint(
                board="机器人", speed_per_min=1.0, amount_total=20.0, lead_change=0.5
            ),
            StrengthBoardPoint(
                board="AI应用", speed_per_min=12.0, amount_total=240.0, lead_change=5.0
            ),
        ),
    )

    events = build_activation_events([frame_a, frame_b], score_threshold=60.0)

    assert len(events) == 1
    assert events[0].strongest_board == "AI应用"
    assert events[0].label == "AI应用"


def test_extract_capital_metrics_supports_qmt_style_rows():
    rows = [
        {
            "date": "2026-04-10",
            "large_inflow": 100.0,
            "large_outflow": 10.0,
            "medium_inflow": 60.0,
            "medium_outflow": 20.0,
            "small_inflow": 30.0,
            "small_outflow": 40.0,
        },
        {
            "date": "2026-04-09",
            "large_inflow": 20.0,
            "large_outflow": 30.0,
            "medium_inflow": 10.0,
            "medium_outflow": 20.0,
        },
        {
            "date": "2026-04-08",
            "large_inflow": 80.0,
            "large_outflow": 10.0,
            "medium_inflow": 40.0,
            "medium_outflow": 10.0,
        },
    ]

    metrics = extract_capital_metrics(rows)

    assert metrics["main_net_inflow"] == 130.0
    assert metrics["recent_positive_days"] == 2
    assert metrics["main_net_inflow_pct"] is not None


def test_ranked_stock_candidates_prioritize_technical_and_capital():
    ranked = build_ranked_stock_candidates(
        [
            StockCandidateMetrics(
                symbol="300001.SZ",
                name="强技术强资金",
                last_price=25.0,
                change_pct=5.2,
                amount=300000000.0,
                technical_raw=90.0,
                capital_raw=88.0,
                fundamental_raw=40.0,
                main_net_inflow_pct=6.2,
                recent_positive_days=4,
                return_5d=12.4,
                return_20d=28.0,
                above_ma20=True,
                technical_coverage=build_technical_coverage(
                    return_5d=12.4,
                    return_20d=28.0,
                    range_position=0.82,
                ),
                capital_coverage=build_capital_coverage(
                    main_net_inflow=42_000_000.0,
                    main_net_inflow_pct=6.2,
                    has_rows=True,
                ),
                fundamental_coverage=build_fundamental_coverage(
                    roe_like=9.0,
                    profit_margin=7.2,
                    debt_ratio=0.46,
                ),
            ),
            StockCandidateMetrics(
                symbol="300002.SZ",
                name="弱技术强基本面",
                last_price=12.0,
                change_pct=0.8,
                amount=50000000.0,
                technical_raw=35.0,
                capital_raw=30.0,
                fundamental_raw=95.0,
                roe_like=16.0,
                profit_margin=15.0,
                debt_ratio=0.31,
                technical_coverage=build_technical_coverage(
                    return_5d=None,
                    return_20d=None,
                    range_position=None,
                ),
                capital_coverage=build_capital_coverage(
                    main_net_inflow=None,
                    main_net_inflow_pct=None,
                    has_rows=False,
                ),
                fundamental_coverage=build_fundamental_coverage(
                    roe_like=16.0,
                    profit_margin=15.0,
                    debt_ratio=0.31,
                ),
            ),
        ]
    )

    assert ranked[0].symbol == "300001.SZ"
    assert ranked[0].quality_score > ranked[1].quality_score
    assert ranked[0].confidence_score > ranked[1].confidence_score
    assert any("主力资金" in reason for reason in ranked[0].selection_reasons)
    assert "技术面样本不足" in ranked[1].risk_flags


def test_ranked_stock_candidates_penalize_missing_data_coverage():
    ranked = build_ranked_stock_candidates(
        [
            StockCandidateMetrics(
                symbol="300010.SZ",
                name="数据完整",
                last_price=18.0,
                change_pct=3.1,
                amount=180000000.0,
                technical_raw=70.0,
                capital_raw=72.0,
                fundamental_raw=65.0,
                recent_positive_days=3,
                return_5d=8.0,
                return_20d=14.0,
                above_ma20=True,
                technical_coverage=100.0,
                capital_coverage=100.0,
                fundamental_coverage=100.0,
            ),
            StockCandidateMetrics(
                symbol="300011.SZ",
                name="数据残缺",
                last_price=18.5,
                change_pct=3.3,
                amount=180000000.0,
                technical_raw=72.0,
                capital_raw=72.0,
                fundamental_raw=65.0,
                recent_positive_days=0,
                technical_coverage=35.0,
                capital_coverage=25.0,
                fundamental_coverage=0.0,
            ),
        ]
    )

    assert ranked[0].symbol == "300010.SZ"
    assert ranked[0].confidence_score > ranked[1].confidence_score
    assert ranked[0].quality_score > ranked[1].quality_score
    assert "基本面覆盖不足" in ranked[1].risk_flags
