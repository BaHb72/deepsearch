from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal

from deepsearch.domain.market_data import (
    AuctionQualityCalculator,
    CapitalPulseCalculator,
    OrderImbalanceCalculator,
    SnapshotBuffer,
)
from deepsearch.ports.market_data import MarketSnapshot, WindowSpec


def _make_snapshot(
        code: str,
        name: str,
        ts: datetime,
        *,
        last: str,
        amount: str,
        volume: int,
        num_trades: int,
        bid_prices: list[str],
        bid_volumes: list[int],
        ask_prices: list[str],
        ask_volumes: list[int],
        upper_limit: str | None = None,
        lower_limit: str | None = None,
        trading_phase: str | None = None,
) -> MarketSnapshot:
    return MarketSnapshot(
        code=code,
        name=name,
        exchange="SSE",
        ts=ts,
        last=Decimal(last),
        open=Decimal(last),
        high=Decimal(last),
        low=Decimal(last),
        prev_close=Decimal(last),
        amount=Decimal(amount),
        volume=volume,
        num_trades=num_trades,
        bid_prices=[Decimal(p) for p in bid_prices],
        bid_volumes=bid_volumes,
        ask_prices=[Decimal(p) for p in ask_prices],
        ask_volumes=ask_volumes,
        upper_limit=Decimal(upper_limit) if upper_limit else None,
        lower_limit=Decimal(lower_limit) if lower_limit else None,
        trading_phase=trading_phase,
    )


def test_capital_pulse_calculator_basic() -> None:
    retention = timedelta(minutes=5)
    buffer = SnapshotBuffer(retention)
    now = datetime(2025, 10, 21, 9, 35, 0)
    window = WindowSpec(name="1m", duration=timedelta(minutes=1))

    code_a = "000001.SZ"
    code_b = "000002.SZ"
    board_mapping = {"core": (code_a, code_b)}

    resolver = lambda board: board_mapping.get(board, ())
    calculator = CapitalPulseCalculator(
        buffer=buffer,
        resolve_board_codes=resolver,
        data_source="amazingdata",
    )

    buffer.ingest(
        _make_snapshot(
            code_a,
            "样例一",
            now - timedelta(minutes=1),
            last="10.0",
            amount="1000000",
            volume=100000,
            num_trades=1000,
            bid_prices=["9.99"] * 5,
            bid_volumes=[1000, 900, 800, 700, 600],
            ask_prices=["10.01"] * 5,
            ask_volumes=[900, 800, 700, 600, 500],
        )
    )
    buffer.ingest(
        _make_snapshot(
            code_b,
            "样例二",
            now - timedelta(minutes=1),
            last="20.0",
            amount="800000",
            volume=80000,
            num_trades=800,
            bid_prices=["19.98"] * 5,
            bid_volumes=[800, 700, 600, 500, 400],
            ask_prices=["20.02"] * 5,
            ask_volumes=[700, 600, 500, 400, 300],
        )
    )

    buffer.ingest(
        _make_snapshot(
            code_a,
            "样例一",
            now,
            last="10.5",
            amount="1600000",
            volume=120000,
            num_trades=1200,
            bid_prices=["10.49"] * 5,
            bid_volumes=[1100, 900, 800, 700, 600],
            ask_prices=["10.51"] * 5,
            ask_volumes=[800, 700, 600, 500, 400],
        )
    )
    buffer.ingest(
        _make_snapshot(
            code_b,
            "样例二",
            now,
            last="21.0",
            amount="950000",
            volume=90000,
            num_trades=900,
            bid_prices=["20.98"] * 5,
            bid_volumes=[850, 750, 650, 550, 450],
            ask_prices=["21.02"] * 5,
            ask_volumes=[750, 650, 550, 450, 350],
        )
    )

    entry = calculator.compute("core", window, as_of=now)
    assert entry is not None
    # delta amount: (1_600_000 - 1_000_000) + (950_000 - 800_000) = 750_000
    assert entry.amount_total == Decimal("750000")
    assert entry.speed_per_min == Decimal("750000")
    assert entry.accel_per_min2 == Decimal("0")

    # 第二次计算模拟加速
    later = now + timedelta(minutes=1)
    buffer.ingest(
        _make_snapshot(
            code_a,
            "样例一",
            later,
            last="11.0",
            amount="2200000",
            volume=150000,
            num_trades=1500,
            bid_prices=["10.99"] * 5,
            bid_volumes=[1200, 1000, 900, 800, 700],
            ask_prices=["11.01"] * 5,
            ask_volumes=[900, 800, 700, 600, 500],
        )
    )
    buffer.ingest(
        _make_snapshot(
            code_b,
            "样例二",
            later,
            last="21.5",
            amount="1150000",
            volume=105000,
            num_trades=1050,
            bid_prices=["21.48"] * 5,
            bid_volumes=[900, 800, 700, 600, 500],
            ask_prices=["21.52"] * 5,
            ask_volumes=[800, 700, 600, 500, 400],
        )
    )

    second = calculator.compute("core", window, as_of=later)
    assert second is not None
    delta_second = (Decimal("2200000") - Decimal("1600000")) + (
            Decimal("1150000") - Decimal("950000")
    )
    assert second.amount_total == delta_second
    assert second.speed_per_min == delta_second
    assert second.accel_per_min2 == delta_second - Decimal("750000")


def test_auction_quality_price_stability() -> None:
    retention = timedelta(minutes=10)
    buffer = SnapshotBuffer(retention)
    now = datetime(2025, 10, 21, 9, 24, 0)
    window = WindowSpec(name="auction", duration=timedelta(minutes=5))
    code = "000001.SZ"
    resolver = lambda board: (code,) if board == "auction_board" else ()
    calculator = AuctionQualityCalculator(
        buffer=buffer,
        resolve_board_codes=resolver,
        data_source="amazingdata",
        price_window=timedelta(minutes=5),
    )

    samples = [
        (5, "10.12", "500000", 50000, 10),
        (4, "10.14", "550000", 55000, 20),
        (3, "10.16", "600000", 60000, 30),
        (2, "10.18", "650000", 65000, 40),
        (1, "10.19", "700000", 70000, 50),
    ]
    for offset_minutes, price, amount, volume, trades in samples:
        buffer.ingest(
            _make_snapshot(
                code,
                "竞价标的",
                now - timedelta(minutes=offset_minutes),
                last=price,
                amount=amount,
                volume=volume,
                num_trades=trades,
                bid_prices=["9.9"] * 5,
                bid_volumes=[500] * 5,
                ask_prices=["10.1"] * 5,
                ask_volumes=[400] * 5,
                trading_phase="C",
            )
        )
    buffer.ingest(
        _make_snapshot(
            code,
            "竞价标的",
            now,
            last="10.20",
            amount="750000",
            volume=80000,
            num_trades=60,
            bid_prices=["10.18"] * 5,
            bid_volumes=[600] * 5,
            ask_prices=["10.22"] * 5,
            ask_volumes=[500] * 5,
            trading_phase="C",
        )
    )

    entry = calculator.compute("auction_board", window, as_of=now)
    assert entry is not None

    amount_delta = Decimal("750000") - Decimal("500000")
    assert entry.amount_acc == amount_delta

    price_samples = [
        Decimal("10.12"),
        Decimal("10.14"),
        Decimal("10.16"),
        Decimal("10.18"),
        Decimal("10.19"),
        Decimal("10.20"),
    ]
    mean = sum(price_samples) / Decimal(len(price_samples))
    expected_variance = sum((value - mean) ** 2 for value in price_samples) / Decimal(
        len(price_samples)
    )
    assert entry.price_stability == expected_variance


def test_order_imbalance_metrics() -> None:
    retention = timedelta(minutes=5)
    buffer = SnapshotBuffer(retention)
    calculator = OrderImbalanceCalculator(
        buffer=buffer,
        data_source="amazingdata",
    )
    window = WindowSpec(name="1m", duration=timedelta(minutes=1))
    now = datetime(2025, 10, 21, 10, 0, 0)
    code = "000001.SZ"

    buffer.ingest(
        _make_snapshot(
            code,
            "盘口标的",
            now - timedelta(minutes=1),
            last="15.00",
            amount="1000000",
            volume=100000,
            num_trades=100,
            bid_prices=["14.99", "14.98", "14.97", "14.96", "14.95"],
            bid_volumes=[100, 90, 80, 70, 60],
            ask_prices=["15.01", "15.02", "15.03", "15.04", "15.05"],
            ask_volumes=[90, 80, 70, 60, 50],
        )
    )

    buffer.ingest(
        _make_snapshot(
            code,
            "盘口标的",
            now,
            last="15.10",
            amount="1150000",
            volume=110000,
            num_trades=150,
            bid_prices=["15.09", "15.08", "15.07", "15.06", "15.05"],
            bid_volumes=[120, 100, 90, 80, 70],
            ask_prices=["15.11", "15.12", "15.13", "15.14", "15.15"],
            ask_volumes=[80, 70, 60, 50, 40],
        )
    )

    entry = calculator.evaluate(code, window, as_of=now)
    assert entry is not None

    bid_total = sum([120, 100, 90, 80, 70])
    ask_total = sum([80, 70, 60, 50, 40])
    expected_obi = Decimal(bid_total - ask_total) / Decimal(bid_total + ask_total)
    assert entry.obi == expected_obi

    delta_amount = Decimal("1150000") - Decimal("1000000")
    expected_speed = delta_amount
    mid = (Decimal("15.11") + Decimal("15.09")) / Decimal("2")
    spread = Decimal("15.11") - Decimal("15.09")
    expected_eis = (spread / mid) * expected_speed
    assert entry.eis == expected_eis
    assert entry.ntm == Decimal(50)
