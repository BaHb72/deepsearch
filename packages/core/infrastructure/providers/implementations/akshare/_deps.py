"""AkShare 依赖加载与最小协议定义"""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Any, Optional, Protocol, cast

if TYPE_CHECKING:  # pragma: no cover - 仅用于类型检查
    from pandas import DataFrame, Series
else:  # pragma: no cover - 运行期无需真实类型

    class DataFrame:  # type: ignore[pyanalyze]
        """运行期的占位类，用于描述 pandas.DataFrame"""

    class Series:  # type: ignore[pyanalyze]
        """运行期的占位类，用于描述 pandas.Series"""


class AkshareModule(Protocol):
    """描述当前模块使用到的 AkShare API"""

    def stock_individual_info_em(self, *, symbol: str) -> DataFrame: ...

    def stock_zh_a_hist(self, *args: Any, **kwargs: Any) -> DataFrame: ...

    def stock_zh_a_hist_min_em(self, *args: Any, **kwargs: Any) -> DataFrame: ...

    def stock_zh_a_spot_em(self, *args: Any, **kwargs: Any) -> DataFrame: ...

    def stock_info_a_code_name(self, *args: Any, **kwargs: Any) -> DataFrame: ...

    def stock_board_concept_name_ths(self, *args: Any, **kwargs: Any) -> DataFrame: ...

    def stock_board_concept_name_em(self, *args: Any, **kwargs: Any) -> DataFrame: ...

    def stock_board_concept_index_ths(
        self, symbol: str, start_date: str, end_date: str
    ) -> DataFrame: ...

    def stock_board_concept_info_ths(self, symbol: str) -> DataFrame: ...

    def stock_board_concept_cons_em(self, *args: Any, **kwargs: Any) -> DataFrame: ...

    def stock_board_concept_summary_ths(self, *args: Any, **kwargs: Any) -> DataFrame: ...

    def stock_board_industry_name_em(self, *args: Any, **kwargs: Any) -> DataFrame: ...

    def stock_board_industry_cons_em(self, *args: Any, **kwargs: Any) -> DataFrame: ...

    def stock_individual_fund_flow(self, *args: Any, **kwargs: Any) -> DataFrame: ...

    def stock_sector_fund_flow_rank(self, *args: Any, **kwargs: Any) -> DataFrame: ...

    def stock_margin_sse(self, *args: Any, **kwargs: Any) -> DataFrame: ...

    def stock_dzjy_mrmx(self, *args: Any, **kwargs: Any) -> DataFrame: ...

    def stock_hsgt_hist_em(self, *args: Any, **kwargs: Any) -> DataFrame: ...

    def stock_zt_pool_em(self, *args: Any, **kwargs: Any) -> DataFrame: ...

    def stock_zt_pool_dtgc_em(self, *args: Any, **kwargs: Any) -> DataFrame: ...

    def stock_yjbb_em(self, *args: Any, **kwargs: Any) -> DataFrame: ...

    def stock_yjkb_em(self, *args: Any, **kwargs: Any) -> DataFrame: ...

    def stock_yjyg_em(self, *args: Any, **kwargs: Any) -> DataFrame: ...

    def tool_trade_date_hist_sina(self, *args: Any, **kwargs: Any) -> DataFrame: ...

    def stock_lhb_detail_em(self, *args: Any, **kwargs: Any) -> DataFrame: ...


class PandasModule(Protocol):
    """最小 pandas 模块协议，仅暴露 DataFrame/Series"""

    DataFrame: type[DataFrame]
    Series: type[Series]


def load_akshare() -> Optional[AkshareModule]:
    """尝试加载 AkShare 模块"""

    try:
        module = import_module("akshare")
    except ImportError:
        return None
    return cast(AkshareModule, module)


def load_pandas() -> Optional[PandasModule]:
    """尝试加载 pandas 模块"""

    try:
        module = import_module("pandas")
    except ImportError:
        return None
    return cast(PandasModule, module)
