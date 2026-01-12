"""E2E test for aggregation framework."""

import asyncio

from deepsearch.application.services.aggregation import get_cache
from deepsearch.application.services.unified_data import (
    initialize_unified_feed,
    start_aggregation_engine,
    stop_aggregation_engine,
)


async def test():
    print("Initializing UnifiedDataFeed...")
    initialize_unified_feed()

    print("Starting AggregationEngine...")
    start_aggregation_engine()

    print("Waiting for first computation...")
    await asyncio.sleep(2)

    gainers = get_cache().get("top_gainers")
    losers = get_cache().get("top_losers")

    print("=== RESULTS ===")
    print(f"Gainers cached: {gainers is not None}")
    print(f"Losers cached: {losers is not None}")

    if gainers:
        print(f"Gainers count: {len(gainers)}")
        first = gainers[0]
        print(f"First gainer: {first['symbol']} - {first['name']} ({first['change_pct']}%)")

    if losers:
        print(f"Losers count: {len(losers)}")
        first = losers[0]
        print(f"First loser: {first['symbol']} - {first['name']} ({first['change_pct']}%)")

    print("Stopping engine...")
    stop_aggregation_engine()
    print("Done!")


if __name__ == "__main__":
    asyncio.run(test())
