import asyncio
import time
from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, cast

import pandas as pd
from core.ports.concept_engine import ConceptDataProviderPort
from loguru import logger

# 使用 Dict[str, Any] 替代不存在的 Snapshot 类型
SnapshotType = Dict[str, Any]


@dataclass
class SectorFlowState:
    """State of a single sector's flow metrics"""

    concept_code: str
    concept_name: str
    total_volume: float = 0.0
    total_amount: float = 0.0
    velocity_1min: float = 0.0  # Money flow per minute
    rising_count: int = 0
    falling_count: int = 0
    lead_stock: str = ""
    lead_stock_change: float = 0.0
    last_update_ts: float = 0.0


class ConceptLinkageEngine:
    """
    Core engine for Concept Monitoring and Fund Flow.
    Maintains the static graph of Stock->Concepts and processes real-time snapshots.
    """

    def __init__(self, provider: ConceptDataProviderPort):
        self.provider = provider
        self._concept_map: Dict[str, List[str]] = {}  # ConceptID -> [StockID]
        self._stock_to_concepts: Dict[str, List[str]] = defaultdict(list)  # StockID -> [ConceptID]
        self._concept_names: Dict[str, str] = {}  # ConceptID -> Name
        self._concept_query_codes: Dict[str, List[str]] = (
            {}
        )  # ConceptID -> query codes for provider
        self._constituent_scan_cursor: int = 0
        self._board_fallback_attempted = False

        self._sector_states: Dict[str, SectorFlowState] = {}
        self._stock_snapshots: Dict[str, SnapshotType] = {}  # Cache last snapshot for delta calc

        self._initialized = False

    @staticmethod
    def _normalize_stock_code(stock_code: object) -> str:
        """Normalize stock code across suffix/prefix formats (e.g. 600519.SH / SH600519 / 600519)."""
        token = str(stock_code or "").strip().upper()
        if not token:
            return ""

        digits = "".join(ch for ch in token if ch.isdigit())
        if len(digits) >= 6:
            return digits[-6:]
        return token

    @staticmethod
    def _pick_stock_column(columns: List[str]) -> str:
        candidates = [
            "code",
            "stock_code",
            "symbol",
            "security_code",
            "con_code",
            "CON_CODE",
        ]
        for candidate in candidates:
            if candidate in columns:
                return candidate
        return columns[0]

    @staticmethod
    def _pick_board_columns(columns: List[str]) -> List[str]:
        preferred = [
            "board",
            "board_name",
            "LISTPLATE_NAME",
            "INDUSTRY",
            "industry",
            "plate",
            "PLATE",
            "BLOCK_NAME",
            "板块",
            "所属行业",
        ]
        selected = [name for name in preferred if name in columns]
        if selected:
            return selected

        fuzzy: List[str] = []
        for name in columns:
            token = str(name).lower()
            if any(flag in token for flag in ("board", "plate", "block")) or "板块" in str(name):
                fuzzy.append(name)
        return fuzzy

    @staticmethod
    def _split_board_tokens(raw: object) -> List[str]:
        text = str(raw or "").strip()
        if not text:
            return []

        normalized = (
            text.replace("；", ",")
            .replace("，", ",")
            .replace("、", ",")
            .replace(";", ",")
            .replace("|", ",")
            .replace("/", ",")
        )
        tokens = [token.strip() for token in normalized.split(",") if token.strip()]
        unique: List[str] = []
        for token in tokens:
            if token not in unique:
                unique.append(token)
        return unique

    def _link_stock_to_concept(self, stock_code: object, concept_code: str) -> None:
        raw_key = str(stock_code or "").strip().upper()
        norm_key = self._normalize_stock_code(stock_code)
        keys = [raw_key] if raw_key else []
        if norm_key and norm_key != raw_key:
            keys.append(norm_key)

        for key in keys:
            concepts = self._stock_to_concepts[key]
            if concept_code not in concepts:
                concepts.append(concept_code)

    def _resolve_concepts_for_stock(self, stock_code: str) -> List[str]:
        raw_key = str(stock_code or "").strip().upper()
        norm_key = self._normalize_stock_code(stock_code)
        keys = [raw_key] if raw_key else []
        if norm_key and norm_key != raw_key:
            keys.append(norm_key)

        merged: List[str] = []
        for key in keys:
            for concept_id in self._stock_to_concepts.get(key, []):
                if concept_id not in merged:
                    merged.append(concept_id)
        return merged

    async def initialize_graph(self):
        """Build the static Stock-Concept graph"""
        if self._initialized:
            return

        logger.info("Initializing Concept Linkage Graph...")
        try:
            # 1. Fetch industry list
            industries_df = await self.provider.get_industry_base_info()
            if industries_df.empty:
                logger.warning("No industry data available.")
                return

            # Map Industry Codes and Names
            # Assuming columns from field maps/research: INDEX_CODE, INDUSTRY_CODE, LEVEL1_NAME...
            # We will prioritize LEVEL2 or LEVEL3 for "Concepts" if available, else standard industries
            # Use a simplified approach: map all available rows

            # Note: Checking columns dynamically or assuming from extended.py logic
            for _, row in industries_df.iterrows():
                industry_code = row.get("INDUSTRY_CODE")
                index_code = row.get("INDEX_CODE")
                code = industry_code or index_code
                name = row.get("LEVEL1_NAME")  # Default to L1, refine if L2/L3 exists
                if row.get("LEVEL2_NAME"):
                    name = row.get("LEVEL2_NAME")
                if row.get("LEVEL3_NAME"):
                    name = row.get("LEVEL3_NAME")

                if code and name:
                    concept_id = str(code)
                    self._concept_names[concept_id] = str(name)
                    self._sector_states[concept_id] = SectorFlowState(concept_id, str(name))

                    query_codes: List[str] = []
                    for candidate in (industry_code, index_code, concept_id):
                        value = str(candidate).strip() if candidate else ""
                        if value and value not in query_codes:
                            query_codes.append(value)
                    if query_codes:
                        self._concept_query_codes[concept_id] = query_codes

            # 2. Fetch constituents for *active* comparison concepts
            # Fetching ALL constituents might be slow.
            # Strategy: Fetch top 50 active concepts or let user drive subscription.
            # For MVP: Iterate top 20 concepts or a specific list if defined.
            # Here we just init empty and fill on demand or async background.
            pass

            logger.info(f"Initialized {len(self._concept_names)} concept nodes.")
            self._initialized = True

        except Exception as e:
            logger.error(f"Failed to initialize Concept Graph: {e}")

    async def _fetch_constituents_for_concept(self, code: str) -> tuple[str, List[str]]:
        query_codes = self._concept_query_codes.get(code, [code])
        df = None
        for query_code in query_codes:
            try:
                candidate_df = await asyncio.wait_for(
                    self.provider.get_industry_constituent(query_code),
                    timeout=8.0,
                )
                if candidate_df is not None and not candidate_df.empty:
                    df = candidate_df
                    break
            except Exception as exc:
                logger.debug(f"load_constituents concept={code} query={query_code} failed: {exc}")

        if df is None or df.empty:
            return code, []

        stock_col = self._pick_stock_column(df.columns.tolist())
        raw_stocks = [
            str(item).strip().upper() for item in df[stock_col].tolist() if str(item).strip()
        ]
        stocks: List[str] = []
        for stock_code in raw_stocks:
            if stock_code not in stocks:
                stocks.append(stock_code)
        return code, stocks

    async def load_constituents(self, concept_codes: List[str]):
        """Lazy load constituents for specific concepts"""
        pending = [code for code in concept_codes if code not in self._concept_map]
        if not pending:
            return

        results = await asyncio.gather(
            *(self._fetch_constituents_for_concept(code) for code in pending),
            return_exceptions=True,
        )

        for result in results:
            if isinstance(result, BaseException):
                logger.debug(f"load_constituents failed with exception: {result}")
                continue

            code, stocks = result
            self._concept_map[code] = stocks
            for stock_code in stocks:
                self._link_stock_to_concept(stock_code, code)

    async def _load_stock_list_fallback(self) -> bool:
        """当行业成分接口不可用时，尝试从股票列表板块字段构建概念映射。"""
        if self._board_fallback_attempted:
            return False

        self._board_fallback_attempted = True
        try:
            payload = await self.provider.get_stock_list()
            if payload is None:
                return False

            stock_df = payload if isinstance(payload, pd.DataFrame) else pd.DataFrame(payload)
            if stock_df.empty:
                return False

            code_col = self._pick_stock_column(stock_df.columns.tolist())
            board_cols = self._pick_board_columns(stock_df.columns.tolist())
            if not board_cols:
                logger.warning("Stock list fallback missing board columns.")
                return False

            board_to_stocks: Dict[str, List[str]] = defaultdict(list)
            for _, row in stock_df.iterrows():
                stock_code = self._normalize_stock_code(row.get(code_col))
                if not stock_code:
                    continue

                board_tokens: List[str] = []
                for col in board_cols:
                    board_tokens.extend(self._split_board_tokens(row.get(col)))

                if not board_tokens:
                    continue

                for board_name in board_tokens:
                    concept_id = f"BOARD::{board_name}"
                    linked = board_to_stocks[concept_id]
                    if stock_code not in linked:
                        linked.append(stock_code)

            if not board_to_stocks:
                return False

            for concept_id, stocks in board_to_stocks.items():
                if not stocks:
                    continue
                if concept_id not in self._concept_names:
                    name = concept_id.split("BOARD::", 1)[1]
                    self._concept_names[concept_id] = name
                    self._sector_states[concept_id] = SectorFlowState(concept_id, name)

                self._concept_map[concept_id] = stocks
                for stock_code in stocks:
                    self._link_stock_to_concept(stock_code, concept_id)

            logger.info(f"Stock list fallback loaded concepts={len(board_to_stocks)}")
            return True
        except Exception as exc:
            logger.warning(f"Stock list fallback failed: {exc}")
            return False

    async def ensure_stock_linkage(
        self,
        stock_code: str,
        batch_size: int = 10,
        max_batches: int = 3,
        time_budget_seconds: float = 20.0,
    ) -> None:
        """Ensure concept linkage index exists for the given stock by lazy-loading concept constituents."""
        if not self._initialized:
            await self.initialize_graph()

        if not stock_code:
            return
        if self._resolve_concepts_for_stock(stock_code):
            return

        all_codes = list(self._concept_names.keys())
        if not all_codes:
            return

        start_ts = time.time()
        total_codes = len(all_codes)
        offset = self._constituent_scan_cursor % total_codes
        scanned = 0
        batches = 0
        target = self._normalize_stock_code(stock_code)
        logger.info(
            f"Ensuring linkage for stock={stock_code} normalized={target}, "
            f"total_concepts={total_codes}, start_offset={offset}"
        )

        while scanned < total_codes:
            if batches >= max_batches:
                break
            if (time.time() - start_ts) >= time_budget_seconds:
                break

            batch: List[str] = []
            while len(batch) < batch_size and scanned < total_codes:
                concept_code = all_codes[(offset + scanned) % total_codes]
                scanned += 1
                if concept_code in self._concept_map:
                    continue
                batch.append(concept_code)

            if not batch:
                continue

            await self.load_constituents(batch)
            batches += 1
            if self._resolve_concepts_for_stock(stock_code):
                self._constituent_scan_cursor = (offset + scanned) % total_codes
                logger.info(
                    f"Linkage resolved for stock={stock_code} after batches={batches}, scanned={scanned}"
                )
                return

        self._constituent_scan_cursor = (offset + scanned) % total_codes
        logger.info(
            f"Linkage not resolved yet for stock={stock_code}, batches={batches}, scanned={scanned}, "
            f"elapsed={time.time() - start_ts:.2f}s"
        )

        if await self._load_stock_list_fallback() and self._resolve_concepts_for_stock(stock_code):
            logger.info(f"Linkage resolved via stock-list fallback for stock={stock_code}")

    def process_snapshot(self, snapshot: dict) -> List[str]:
        """
        Process a single stock snapshot update.
        Returns list of Concept IDs that need update.
        """
        stock_code = snapshot.get("code")
        if not stock_code:
            return []

        affected_concepts = self._resolve_concepts_for_stock(str(stock_code))
        if not affected_concepts:
            return []

        # Calculate Delta (Turnover/Amount)
        prev_snap = self._stock_snapshots.get(stock_code)

        # Parse fields
        current_amount = float(snapshot.get("amount", 0))
        current_last = float(snapshot.get("last", 0))
        current_pre_close = float(snapshot.get("pre_close", 0))

        delta_amount = 0.0
        if prev_snap:
            prev_amount = float(prev_snap.get("amount", 0))
            if current_amount > prev_amount:
                delta_amount = current_amount - prev_amount
        else:
            # First snapshot, ignore large delta or assume 0 start?
            # Treat strictly as delta from subscription start
            delta_amount = 0

        self._stock_snapshots[stock_code] = snapshot

        change_pct = 0.0
        if current_pre_close > 0:
            change_pct = (current_last - current_pre_close) / current_pre_close

        updated_sectors = []
        now = time.time()

        for concept_id in affected_concepts:
            state = self._sector_states.get(concept_id)
            if not state:
                continue

            # Update State
            # Simple windowed velocity: decay old + add new
            # Alpha/Decay factor for smooth EMA of velocity
            alpha = 0.1
            state.velocity_1min = (state.velocity_1min * (1 - alpha)) + (delta_amount * alpha)
            state.total_amount += delta_amount
            state.last_update_ts = now

            # Update Lead Stock if this one is stronger
            if abs(change_pct) > abs(state.lead_stock_change) or state.lead_stock == "":
                state.lead_stock = stock_code
                state.lead_stock_change = change_pct

            updated_sectors.append(concept_id)

        return updated_sectors

    async def start(self):
        """Start monitoring - subscribe to market snapshots"""
        if not self._initialized:
            await self.initialize_graph()

        # Subscribe to strict list or all?
        # For full market flow, we need ALL stocks.
        # Assuming provider has 'subscribe_all' or we pass a big list.
        # If 'subscribe_all' implies huge traffic, we might limit to top 500.
        # For this prototype: subscribe to a known list or just rely on shared subscription if available.

        # We will define a callback wrapper
        async def _on_snapshot(data: List[dict] | dict):
            # Data might be list or dict
            if isinstance(data, list):
                for item in data:
                    self.process_snapshot(item)
            else:
                self.process_snapshot(data)

        # Use provider to subscribe. Assuming 'subscribe_stock_snapshot' takes code_list
        # If code_list is None/Empty, does it mean All? Check provider docs.
        # Safest is to get stock list first.
        try:
            # get_stock_list is usually available
            stocks = await self.provider.get_stock_list()
            code_list = stocks["code"].tolist()[:500]  # Top 500 for perf safety in prototype

            await self.provider.subscribe_stock_snapshot(code_list, _on_snapshot)
            logger.info(f"ConceptEngine started monitoring {len(code_list)} stocks.")
        except Exception as e:
            logger.error(f"Failed to start ConceptEngine data feed: {e}")

    def get_sector_velocity_map(self) -> List[dict]:
        """Return heatmap data for valid sectors"""
        results: List[Dict[str, Any]] = []
        for cid, state in self._sector_states.items():
            if state.total_amount > 0:
                results.append(
                    {
                        "concept_code": cid,
                        "name": self._concept_names.get(cid, cid),
                        "velocity": state.velocity_1min,
                        "lead_stock": state.lead_stock,
                        "lead_change": state.lead_stock_change,
                    }
                )
        # Sort by velocity
        results.sort(key=lambda x: cast(float, x["velocity"]), reverse=True)
        return results[:50]  # Top 50 active

    def get_linkage(self, stock_code: str) -> dict:
        """Trace the graph for a specific stock"""
        concepts = self._resolve_concepts_for_stock(stock_code)
        result: Dict[str, Any] = {"center": stock_code, "concepts": []}

        for cid in concepts:
            display_code = cid.split("BOARD::", 1)[1] if cid.startswith("BOARD::") else cid
            c_node: Dict[str, Any] = {
                "code": display_code,
                "name": self._concept_names.get(cid, display_code),
                "peers": [],
            }
            # Find peers (other stocks in this concept)
            # Limit to top 5 for UI clarity?
            all_peers = self._concept_map.get(cid, [])
            # Ideally sort peers by activity/change, but for now just take slice
            peers = all_peers[:5]
            c_node["peers"] = peers
            result["concepts"].append(c_node)

        return result


# Singleton Instance (Lazily instantiated in app or dependency)
_engine_instance: Optional[ConceptLinkageEngine] = None


def get_concept_engine(
    provider: Optional[ConceptDataProviderPort] = None,
) -> Optional[ConceptLinkageEngine]:
    global _engine_instance
    if _engine_instance is None and provider:
        _engine_instance = ConceptLinkageEngine(provider)
    return _engine_instance
