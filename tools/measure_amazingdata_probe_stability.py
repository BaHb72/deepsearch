"""Measure AmazingData probe stability by repeatedly running check-amazingdata.

Usage:
    uv run --python ./.venv/Scripts/python.exe python tools/measure_amazingdata_probe_stability.py
"""

from __future__ import annotations

import argparse
import json
import statistics
import subprocess
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass
class ProbeRun:
    index: int
    started_at: str
    duration_s: float
    exit_code: int
    status: str
    smoke_status: str
    backconnect_status: str
    parse_ok: bool
    parse_error: str
    output_tail: str


def _extract_payload(raw_text: str) -> dict[str, Any] | None:
    if not raw_text:
        return None

    decoder = json.JSONDecoder()
    best: dict[str, Any] | None = None
    for idx, ch in enumerate(raw_text):
        if ch != "{":
            continue
        try:
            obj, _ = decoder.raw_decode(raw_text[idx:])
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict) and "status" in obj and "checks" in obj:
            best = obj
    return best


def _find_check_status(payload: dict[str, Any], aliases: tuple[str, ...]) -> str:
    checks = payload.get("checks", [])
    if not isinstance(checks, list):
        return "unknown"

    for item in checks:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name", ""))
        status = str(item.get("status", "unknown"))
        for alias in aliases:
            if alias in name:
                return status
    return "unknown"


def _run_once(args: argparse.Namespace, index: int) -> ProbeRun:
    cmd = [
        "uv",
        "run",
        "--python",
        args.python,
        "deepsearch",
        "check-amazingdata",
        args.env,
        "--timeout",
        str(args.timeout),
        "--probe-calendar",
        "--probe-timeout",
        str(args.probe_timeout),
        "--probe-market",
        args.probe_market,
        "--probe-data-type",
        args.probe_data_type,
    ]
    if args.suppress_third_party_output:
        cmd.append("--suppress-third-party-output")
    else:
        cmd.append("--no-suppress-third-party-output")

    start_ts = datetime.now(timezone.utc).isoformat()
    begin = time.perf_counter()
    try:
        completed = subprocess.run(  # noqa: S603
            cmd,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=max(30, int(args.command_timeout)),
        )
        exit_code = completed.returncode
        merged = "\n".join(
            part for part in (completed.stdout.strip(), completed.stderr.strip()) if part
        )
    except subprocess.TimeoutExpired as exc:
        duration = time.perf_counter() - begin
        return ProbeRun(
            index=index,
            started_at=start_ts,
            duration_s=round(duration, 3),
            exit_code=124,
            status="failed",
            smoke_status="unknown",
            backconnect_status="unknown",
            parse_ok=False,
            parse_error=f"timeout: {exc}",
            output_tail="",
        )
    except FileNotFoundError as exc:
        duration = time.perf_counter() - begin
        return ProbeRun(
            index=index,
            started_at=start_ts,
            duration_s=round(duration, 3),
            exit_code=127,
            status="failed",
            smoke_status="unknown",
            backconnect_status="unknown",
            parse_ok=False,
            parse_error=str(exc),
            output_tail="",
        )

    duration = time.perf_counter() - begin
    payload = _extract_payload(merged) or _extract_payload(completed.stdout)
    if payload is None:
        tail = merged.splitlines()[-12:]
        return ProbeRun(
            index=index,
            started_at=start_ts,
            duration_s=round(duration, 3),
            exit_code=exit_code,
            status="failed" if exit_code != 0 else "unknown",
            smoke_status="unknown",
            backconnect_status="unknown",
            parse_ok=False,
            parse_error="无法从命令输出解析诊断 JSON",
            output_tail="\n".join(tail),
        )

    overall = str(payload.get("status", "unknown"))
    smoke_status = _find_check_status(payload, ("真实 API Smoke", "API Smoke"))
    backconnect_status = _find_check_status(payload, ("Scheduler 到 Worker 回连", "Worker 回连"))
    return ProbeRun(
        index=index,
        started_at=start_ts,
        duration_s=round(duration, 3),
        exit_code=exit_code,
        status=overall,
        smoke_status=smoke_status,
        backconnect_status=backconnect_status,
        parse_ok=True,
        parse_error="",
        output_tail="",
    )


def _summarize(runs: list[ProbeRun]) -> dict[str, Any]:
    total = len(runs)
    ok_count = sum(1 for r in runs if r.status.lower() == "ok")
    warning_count = sum(1 for r in runs if r.status.lower() == "warning")
    failed_count = sum(1 for r in runs if r.status.lower() == "failed")
    parse_failed = sum(1 for r in runs if not r.parse_ok)
    smoke_ok = sum(1 for r in runs if r.smoke_status.lower() == "ok")
    backconnect_ok = sum(1 for r in runs if r.backconnect_status.lower() == "ok")
    durations = [r.duration_s for r in runs]

    max_consecutive_failed = 0
    current = 0
    for item in runs:
        if item.status.lower() == "failed":
            current += 1
            max_consecutive_failed = max(max_consecutive_failed, current)
        else:
            current = 0

    return {
        "total_runs": total,
        "ok_runs": ok_count,
        "warning_runs": warning_count,
        "failed_runs": failed_count,
        "parse_failed_runs": parse_failed,
        "smoke_ok_runs": smoke_ok,
        "backconnect_ok_runs": backconnect_ok,
        "ok_rate": round((ok_count / total) if total else 0.0, 4),
        "smoke_ok_rate": round((smoke_ok / total) if total else 0.0, 4),
        "backconnect_ok_rate": round((backconnect_ok / total) if total else 0.0, 4),
        "max_consecutive_failed": max_consecutive_failed,
        "duration_s": {
            "min": round(min(durations), 3) if durations else 0.0,
            "max": round(max(durations), 3) if durations else 0.0,
            "avg": round(statistics.fmean(durations), 3) if durations else 0.0,
            "p95": round(_percentile(durations, 95), 3) if durations else 0.0,
        },
    }


def _percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    if pct <= 0:
        return min(values)
    if pct >= 100:
        return max(values)

    ordered = sorted(values)
    k = (len(ordered) - 1) * (pct / 100.0)
    lower = int(k)
    upper = min(lower + 1, len(ordered) - 1)
    if lower == upper:
        return ordered[lower]
    weight = k - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--env", default="dev", choices=["dev", "prod"], help="运行环境")
    parser.add_argument("--runs", type=int, default=5, help="连续执行次数")
    parser.add_argument("--interval-seconds", type=float, default=2.0, help="轮次间隔（秒）")
    parser.add_argument("--timeout", type=float, default=2.0, help="TCP 检查超时（秒）")
    parser.add_argument("--probe-timeout", type=float, default=20.0, help="真实 probe 超时（秒）")
    parser.add_argument("--probe-market", default="SH", help="probe 市场参数")
    parser.add_argument(
        "--probe-data-type",
        default="int",
        choices=["int", "str"],
        help="probe data_type 参数",
    )
    parser.add_argument(
        "--python",
        default="./.venv/Scripts/python.exe",
        help="uv run 使用的 Python 路径",
    )
    parser.add_argument(
        "--suppress-third-party-output",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="是否抑制第三方终端输出",
    )
    parser.add_argument("--command-timeout", type=int, default=300, help="单次命令最大超时（秒）")
    parser.add_argument("--output", default="", help="结果 JSON 输出路径")
    parser.add_argument(
        "--min-ok-rate",
        type=float,
        default=0.95,
        help="门禁阈值：最低整体 ok_rate（0~1）",
    )
    parser.add_argument(
        "--max-p95-seconds",
        type=float,
        default=30.0,
        help="门禁阈值：最高耗时 p95（秒）",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="启用门禁判定，不满足阈值时返回非 0",
    )
    args = parser.parse_args()

    run_count = max(args.runs, 1)
    interval = max(args.interval_seconds, 0.0)
    runs: list[ProbeRun] = []

    for idx in range(1, run_count + 1):
        result = _run_once(args, idx)
        runs.append(result)
        print(
            f"[{idx}/{run_count}] status={result.status} smoke={result.smoke_status} "
            f"backconnect={result.backconnect_status} duration={result.duration_s:.3f}s "
            f"exit={result.exit_code} parse_ok={result.parse_ok}"
        )
        if interval > 0 and idx < run_count:
            time.sleep(interval)

    summary = _summarize(runs)
    min_ok_rate = min(max(float(args.min_ok_rate), 0.0), 1.0)
    max_p95_seconds = max(float(args.max_p95_seconds), 0.0)
    gate = {
        "min_ok_rate": min_ok_rate,
        "max_p95_seconds": max_p95_seconds,
        "actual_ok_rate": summary["ok_rate"],
        "actual_p95_seconds": summary["duration_s"]["p95"],
        "passed": bool(
            summary["ok_rate"] >= min_ok_rate and summary["duration_s"]["p95"] <= max_p95_seconds
        ),
    }
    payload = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "env": args.env,
        "runs": run_count,
        "settings": {
            "timeout": args.timeout,
            "probe_timeout": args.probe_timeout,
            "probe_market": args.probe_market,
            "probe_data_type": args.probe_data_type,
            "interval_seconds": interval,
            "suppress_third_party_output": bool(args.suppress_third_party_output),
            "python": args.python,
            "command_timeout": args.command_timeout,
        },
        "summary": summary,
        "gate": gate,
        "details": [asdict(item) for item in runs],
    }

    if args.output:
        output_path = Path(args.output)
    else:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = Path("logs") / "reports" / f"amazingdata_probe_stability_{ts}.json"

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print("")
    print("=== Summary ===")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print("=== Gate ===")
    print(json.dumps(gate, ensure_ascii=False, indent=2))
    print(f"Report: {output_path}")

    if args.strict and (
        summary["failed_runs"] > 0
        or summary["parse_failed_runs"] > 0
        or not gate["passed"]
    ):
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
