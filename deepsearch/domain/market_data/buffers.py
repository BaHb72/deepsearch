"""实时行情快照缓冲区。

该模块提供按代码维护的窗口缓存，支持基于时间窗口查询快照序列，
为领域层指标计算器提供稳定的数据输入。
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Deque, Dict, Iterable, Iterator, Mapping, MutableMapping, Sequence

from deepsearch.ports.market_data import MarketSnapshot


@dataclass(slots=True)
class SnapshotBuffer:
    """基于时间窗口的行情快照缓冲。

    Attributes:
        retention: 缓存保留时长，超过时长的数据会被逐步淘汰。
    """

    retention: timedelta
    _store: MutableMapping[str, Deque[MarketSnapshot]] = field(default_factory=dict)

    def ingest(self, snapshot: MarketSnapshot) -> None:
        """写入新的行情快照并根据 retention 清理旧数据。"""

        bucket = self._store.setdefault(snapshot.code, deque())
        if bucket and snapshot.ts < bucket[-1].ts:
            raise ValueError(
                f"行情快照时间戳逆序: {snapshot.code} {snapshot.ts} < {bucket[-1].ts}"
            )

        bucket.append(snapshot)
        self._trim_bucket(bucket, snapshot.ts - self.retention)

    def bulk_ingest(self, snapshots: Iterable[MarketSnapshot]) -> None:
        """批量写入快照。"""

        for snapshot in snapshots:
            self.ingest(snapshot)

    def latest_timestamp(self, codes: Sequence[str] | None = None) -> datetime | None:
        """返回指定代码集合中的最新时间戳。"""

        buckets = self._resolve_buckets(codes)
        latest: datetime | None = None
        for bucket in buckets:
            if bucket:
                ts = bucket[-1].ts
                if latest is None or ts > latest:
                    latest = ts
        return latest

    def window_series(
            self,
            code: str,
            *,
            end: datetime,
            duration: timedelta,
            include_prefetch: bool = True,
    ) -> tuple[list[MarketSnapshot], MarketSnapshot | None]:
        """获取指定代码在时间窗口内的快照序列。

        Args:
            code: 证券代码。
            end: 窗口结束时间（含）。
            duration: 窗口跨度。
            include_prefetch: 是否返回窗口前的最新一条快照，用于差值基准。

        Returns:
            (窗口内快照列表, 窗口前最新快照或 None)。
        """

        bucket = self._store.get(code)
        if not bucket:
            return [], None

        start = end - duration
        window: list[MarketSnapshot] = []
        prefix: MarketSnapshot | None = None

        for snapshot in bucket:
            if snapshot.ts < start:
                prefix = snapshot
                continue
            if snapshot.ts > end:
                break
            window.append(snapshot)

        if include_prefetch:
            return window, prefix
        return window, None

    def sliced_series(
            self,
            codes: Sequence[str],
            *,
            end: datetime,
            duration: timedelta,
            include_prefetch: bool = True,
    ) -> Mapping[str, tuple[list[MarketSnapshot], MarketSnapshot | None]]:
        """批量获取窗口内快照序列。"""

        result: Dict[str, tuple[list[MarketSnapshot], MarketSnapshot | None]] = {}
        for code in codes:
            result[code] = self.window_series(
                code,
                end=end,
                duration=duration,
                include_prefetch=include_prefetch,
            )
        return result

    def _resolve_buckets(
            self, codes: Sequence[str] | None
    ) -> Iterator[Deque[MarketSnapshot]]:
        if codes is None:
            yield from self._store.values()
            return

        for code in codes:
            bucket = self._store.get(code)
            if bucket:
                yield bucket

    def _trim_bucket(self, bucket: Deque[MarketSnapshot], threshold: datetime) -> None:
        while bucket and bucket[0].ts < threshold:
            bucket.popleft()

    def latest_snapshot(self, codes: Sequence[str] | None = None) -> MarketSnapshot | None:
        """返回指定标的集合中最新的快照。"""

        latest: MarketSnapshot | None = None
        for bucket in self._resolve_buckets(codes):
            if not bucket:
                continue
            candidate = bucket[-1]
            if latest is None or candidate.ts > latest.ts:
                latest = candidate
        return latest
