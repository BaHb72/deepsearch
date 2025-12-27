from typing import Any, Dict, List, Optional

def subscribe_quote(*args: Any, **kwargs: Any) -> Any: ...
def unsubscribe_quote(*args: Any, **kwargs: Any) -> Any: ...

# MiniQMT API methods
def get_stock_list_in_sector(sector: str) -> List[str]: ...
def get_instrument_detail(symbol: str) -> Dict[str, Any]: ...
def get_instrument_detail_list(symbols: List[str]) -> Dict[str, Dict[str, Any]]: ...
def get_market_data_ex(
    fields: List[str],
    stock_list: List[str],
    period: str = ...,
    start_time: str = ...,
    end_time: str = ...,
    count: int = ...,
    dividend_type: str = ...,
    fill_data: bool = ...,
) -> Dict[str, Any]: ...
def get_market_data(
    fields: List[str] = ...,
    stock_list: List[str] = ...,
    period: str = ...,
    start_time: str = ...,
    end_time: str = ...,
    count: int = ...,
    dividend_type: str = ...,
    fill_data: bool = ...,
    field_list: Optional[List[str]] = ...,
) -> Dict[str, Any]: ...
def get_trading_dates(
    market: str = ...,
    start_time: str = ...,
    end_time: str = ...,
) -> List[str]: ...
def get_holidays() -> List[str]: ...
def get_sector_list() -> List[str]: ...
def get_index_weight(index_code: str) -> Dict[str, float]: ...
def get_full_tick(symbol_list: List[str]) -> Dict[str, Any]: ...
def download_history_data(
    symbol: str,
    period: str,
    start_time: str = ...,
    end_time: str = ...,
    count: int = ...,
) -> None: ...
def download_sector_data() -> None: ...
def download_financial_data(symbols: List[str]) -> None: ...
def get_financial_data(
    symbols: List[str],
    tables: List[str],
) -> Dict[str, Any]: ...
def download_etf_info() -> None: ...
def get_etf_info(symbol: str) -> Dict[str, Any]: ...
def download_index_weight() -> None: ...
def get_divid_factors(symbol: str) -> Dict[str, Any]: ...
def get_markets() -> List[str]: ...
def get_period_list() -> List[str]: ...

__all__ = [
    "subscribe_quote",
    "unsubscribe_quote",
    "get_stock_list_in_sector",
    "get_instrument_detail",
    "get_instrument_detail_list",
    "get_market_data_ex",
    "get_market_data",
    "get_trading_dates",
    "get_holidays",
    "get_sector_list",
    "get_index_weight",
    "get_full_tick",
    "download_history_data",
    "download_sector_data",
    "download_financial_data",
    "get_financial_data",
    "download_etf_info",
    "get_etf_info",
    "download_index_weight",
    "get_divid_factors",
    "get_markets",
    "get_period_list",
]
