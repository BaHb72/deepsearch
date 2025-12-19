
import asyncio
from typing import Any, Dict, List, Optional, Set
from collections import defaultdict
import time
from dataclasses import dataclass, field
from loguru import logger
import pandas as pd

from deepsearch.infrastructure.providers.implementations.amazingdata.amazingdata_extended import AmazingDataExtended

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
    
    def __init__(self, provider: AmazingDataExtended):
        self.provider = provider
        self._concept_map: Dict[str, List[str]] = {}  # ConceptID -> [StockID]
        self._stock_to_concepts: Dict[str, List[str]] = defaultdict(list) # StockID -> [ConceptID]
        self._concept_names: Dict[str, str] = {} # ConceptID -> Name
        
        self._sector_states: Dict[str, SectorFlowState] = {}
        self._stock_snapshots: Dict[str, SnapshotType] = {} # Cache last snapshot for delta calc
        
        self._initialized = False

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
                code = row.get('INDUSTRY_CODE') or row.get('INDEX_CODE')
                name = row.get('LEVEL1_NAME') # Default to L1, refine if L2/L3 exists
                if row.get('LEVEL2_NAME'): name = row.get('LEVEL2_NAME')
                if row.get('LEVEL3_NAME'): name = row.get('LEVEL3_NAME')
                
                if code and name:
                    self._concept_names[str(code)] = str(name)
                    self._sector_states[str(code)] = SectorFlowState(str(code), str(name))

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

    async def load_constituents(self, concept_codes: List[str]):
        """Lazy load constituents for specific concepts"""
        for code in concept_codes:
            if code in self._concept_map:
                continue # Already loaded
                
            df = await self.provider.get_industry_constituent(code)
            if not df.empty:
                # Assuming 'stock_code' or similar column. The mock probe failed so we infer.
                # Usually 'code' or 'symbol'
                stock_col = 'code' if 'code' in df.columns else df.columns[0]
                stocks = df[stock_col].tolist()
                self._concept_map[code] = stocks
                for s in stocks:
                    self._stock_to_concepts[s].append(code)
    
    def process_snapshot(self, snapshot: dict) -> List[str]:
        """
        Process a single stock snapshot update.
        Returns list of Concept IDs that need update.
        """
        stock_code = snapshot.get('code')
        if not stock_code: 
            return []
            
        affected_concepts = self._stock_to_concepts.get(stock_code, [])
        if not affected_concepts:
            return []
            
        # Calculate Delta (Turnover/Amount)
        prev_snap = self._stock_snapshots.get(stock_code)
        
        # Parse fields
        current_amount = float(snapshot.get('amount', 0))
        current_last = float(snapshot.get('last', 0))
        current_pre_close = float(snapshot.get('pre_close', 0))
        
        delta_amount = 0.0
        if prev_snap:
            prev_amount = float(prev_snap.get('amount', 0))
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
            if not state: continue
            
            # Update State
            # Simple windowed velocity: decay old + add new
            # Alpha/Decay factor for smooth EMA of velocity
            alpha = 0.1 
            state.velocity_1min = (state.velocity_1min * (1-alpha)) + (delta_amount * alpha)
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
             code_list = stocks['code'].tolist()[:500] # Top 500 for perf safety in prototype
             
             await self.provider.subscribe_stock_snapshot(code_list, _on_snapshot)
             logger.info(f"ConceptEngine started monitoring {len(code_list)} stocks.")
        except Exception as e:
             logger.error(f"Failed to start ConceptEngine data feed: {e}")

    def get_sector_velocity_map(self) -> List[dict]:
        """Return heatmap data for valid sectors"""
        results = []
        for cid, state in self._sector_states.items():
            if state.total_amount > 0:
                results.append({
                    "concept_code": cid,
                    "name": self._concept_names.get(cid, cid),
                    "velocity": state.velocity_1min,
                    "lead_stock": state.lead_stock,
                    "lead_change": state.lead_stock_change
                })
        # Sort by velocity
        results.sort(key=lambda x: x['velocity'], reverse=True)
        return results[:50] # Top 50 active

    def get_linkage(self, stock_code: str) -> dict:
        """Trace the graph for a specific stock"""
        concepts = self._stock_to_concepts.get(stock_code, [])
        result = {
            "center": stock_code,
            "concepts": []
        }
        
        for cid in concepts:
            c_node = {
                "code": cid,
                "name": self._concept_names.get(cid, cid),
                "peers": []
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

def get_concept_engine(provider: Optional[AmazingDataExtended] = None) -> ConceptLinkageEngine:
    global _engine_instance
    if _engine_instance is None and provider:
        _engine_instance = ConceptLinkageEngine(provider)
    return _engine_instance
