"""
AkShare API 映射配置
标准化所有 AkShare API 的路径和参数映射
"""

import json
from pathlib import Path
from typing import Any, Dict, Optional

from loguru import logger


class AkShareAPIMapping:
    """AkShare API 映射管理器"""

    # API 函数映射表
    API_FUNCTIONS: Dict[str, Dict[str, Any]] = {
        # 实时行情类
        "stock_zh_a_spot_em": {
            "description": "A股实时行情",
            "params": [],
            "cache_ttl": 5,  # 实时数据5秒缓存
            "category": "realtime",
        },
        "stock_zh_b_spot_em": {
            "description": "B股实时行情",
            "params": [],
            "cache_ttl": 5,  # 实时数据5秒缓存
            "category": "realtime",
        },
        "stock_kc_a_spot_em": {
            "description": "科创板实时行情",
            "params": [],
            "cache_ttl": 5,  # 实时数据5秒缓存
            "category": "realtime",
        },
        "stock_zh_index_spot_em": {
            "description": "指数实时行情",
            "params": [],
            "cache_ttl": 5,  # 实时数据5秒缓存
            "category": "realtime",
        },
        "stock_zh_a_st_em": {
            "description": "ST股票列表",
            "params": [],
            "cache_ttl": 300,  # ST列表变化较少，5分钟缓存
            "category": "realtime",
        },
        # 历史数据类
        "stock_zh_a_hist": {
            "description": "A股历史K线",
            "params": ["symbol", "period", "start_date", "end_date", "adjust", "timeout"],
            "param_defaults": {
                "period": "daily",
                "adjust": "",
                "timeout": None,
                "start_date": "19900101",
                "end_date": "20500101",
            },
            "param_transform": {
                "start_date": lambda x: x.replace("-", "") if x else "19900101",
                "end_date": lambda x: x.replace("-", "") if x else "20500101",
            },
            "cache_ttl": 300,
            "category": "historical",
        },
        "stock_zh_a_hist_min_em": {
            "description": "A股分钟K线",
            "params": ["symbol", "start_date", "end_date", "period", "adjust"],
            "param_defaults": {"period": "1", "adjust": ""},
            "cache_ttl": 60,
            "category": "minute",
        },
        # 个股信息类
        "stock_individual_info_em": {
            "description": "个股详细信息",
            "params": ["symbol"],
            "cache_ttl": 3600,
            "category": "info",
        },
        "stock_info_a_code_name": {
            "description": "股票代码名称映射",
            "params": [],
            "cache_ttl": 86400,  # 24小时
            "category": "info",
        },
        # 筹码分布类
        "stock_cyq_em": {
            "description": "筹码分布数据",
            "params": ["symbol", "adjust"],
            "param_defaults": {"adjust": "qfq"},
            "cache_ttl": 300,
            "category": "technical",
        },
        # 市场统计类
        "stock_sse_summary": {
            "description": "上交所市场总貌",
            "params": [],
            "cache_ttl": 300,
            "category": "market",
        },
        "stock_szse_summary": {
            "description": "深交所市场总貌",
            "params": ["date"],
            "param_transform": {"date": lambda x: x.replace("-", "") if x else None},
            "cache_ttl": 300,
            "category": "market",
        },
        # 涨跌停和异动数据类
        "stock_zt_pool_em": {
            "description": "涨停池数据",
            "params": ["date"],
            "param_defaults": {"date": None},  # None表示最新数据
            "param_transform": {"date": lambda x: x.replace("-", "") if x else None},
            "cache_ttl": 30,  # 30秒缓存
            "category": "anomaly",
        },
        "stock_zt_pool_previous_em": {
            "description": "昨日涨停股池",
            "params": ["date"],
            "param_defaults": {"date": None},
            "param_transform": {"date": lambda x: x.replace("-", "") if x else None},
            "cache_ttl": 30,
            "category": "anomaly",
        },
        "stock_zt_pool_dtgc_em": {
            "description": "跌停池数据",
            "params": ["date"],
            "param_defaults": {"date": None},
            "param_transform": {"date": lambda x: x.replace("-", "") if x else None},
            "cache_ttl": 30,
            "category": "anomaly",
        },
        "stock_zt_pool_strong_em": {
            "description": "强势股池",
            "params": ["date"],
            "param_defaults": {"date": None},
            "param_transform": {"date": lambda x: x.replace("-", "") if x else None},
            "cache_ttl": 30,
            "category": "anomaly",
        },
        "stock_zt_pool_sub_new_em": {
            "description": "次新股池",
            "params": ["date"],
            "param_defaults": {"date": None},
            "param_transform": {"date": lambda x: x.replace("-", "") if x else None},
            "cache_ttl": 30,
            "category": "anomaly",
        },
        # 板块数据类
        "stock_board_industry_name_em": {
            "description": "行业板块名称",
            "params": [],
            "cache_ttl": 600,  # 板块名称变化少，10分钟缓存
            "category": "sector",
        },
        "stock_board_concept_name_em": {
            "description": "概念板块名称",
            "params": [],
            "cache_ttl": 600,  # 板块名称变化少，10分钟缓存
            "category": "sector",
        },
        "stock_board_industry_cons_em": {
            "description": "行业板块成份股",
            "params": ["symbol"],
            "cache_ttl": 300,
            "category": "sector",
        },
        "stock_board_concept_cons_em": {
            "description": "概念板块成份股",
            "params": ["symbol"],
            "cache_ttl": 300,
            "category": "sector",
        },
        # 同花顺概念板块数据
        "stock_board_concept_name_ths": {
            "description": "同花顺概念板块名称",
            "params": [],
            "cache_ttl": 3600,  # 1小时缓存
            "category": "sector",
        },
        "stock_board_concept_index_ths": {
            "description": "同花顺概念板块指数",
            "params": ["symbol", "start_date", "end_date"],
            "param_defaults": {"start_date": "20200101", "end_date": "20250321"},
            "param_transform": {
                "start_date": lambda x: x.replace("-", "") if x else "20200101",
                "end_date": lambda x: x.replace("-", "") if x else "20250321",
            },
            "cache_ttl": 300,  # 5分钟缓存
            "category": "sector",
        },
        "stock_board_concept_info_ths": {
            "description": "同花顺概念板块简介",
            "params": ["symbol"],
            "cache_ttl": 3600,  # 1小时缓存
            "category": "sector",
        },
        "stock_board_concept_cons_ths": {
            "description": "同花顺概念板块成份股",
            "params": ["symbol"],
            "cache_ttl": 300,  # 5分钟缓存
            "category": "sector",
        },
        # 沪深港通数据类
        "stock_hsgt_hist_em": {
            "description": "沪深港通历史数据",
            "params": ["symbol"],
            "param_defaults": {"symbol": "沪股通"},
            "cache_ttl": 60,
            "category": "hsgt",
        },
        "stock_hsgt_hold_stock_em": {
            "description": "沪深港通持股排行",
            "params": ["market", "indicator"],
            "param_defaults": {"market": "北向", "indicator": "今日排行"},
            "cache_ttl": 60,
            "category": "hsgt",
        },
        "stock_hsgt_stock_statistics_em": {
            "description": "沪深港通每日个股统计",
            "params": ["symbol", "start_date", "end_date", "market", "indicator"],
            "param_defaults": {"market": "北向", "indicator": "沪股通"},
            "cache_ttl": 60,
            "category": "hsgt",
        },
        "stock_hsgt_fund_flow_summary_em": {
            "description": "沪深港通资金流向汇总",
            "params": [],
            "param_defaults": {},
            "cache_ttl": 30,
            "category": "hsgt",
        },
        "stock_em_hsgt_north_net_flow_in": {
            "description": "北向资金净流入（兼容旧版）",
            "params": ["indicator"],
            "param_defaults": {"indicator": "沪股通"},
            "cache_ttl": 30,
            "category": "hsgt",
        },
        # 分时和盘口数据类
        "stock_intraday_em": {
            "description": "个股分时数据",
            "params": ["symbol"],
            "cache_ttl": 10,
            "category": "intraday",
        },
        "stock_bid_ask_em": {
            "description": "买卖盘口数据",
            "params": ["symbol"],
            "cache_ttl": 5,
            "category": "orderbook",
        },
        # 限售解禁类
        "stock_restricted_release_queue_em": {
            "description": "限售解禁队列",
            "params": ["symbol"],
            "cache_ttl": 3600,  # 1小时缓存
            "category": "restriction",
        },
        "stock_restricted_release_stockholder_em": {
            "description": "限售解禁股东",
            "params": ["symbol", "date"],
            "param_transform": {"date": lambda x: x.replace("-", "") if x else None},
            "cache_ttl": 3600,
            "category": "restriction",
        },
        # 股东信息类
        "stock_circulate_stock_holder": {
            "description": "流通股东",
            "params": ["symbol"],
            "cache_ttl": 3600,
            "category": "holder",
        },
        # 板块行情类
        "stock_sector_spot": {
            "description": "板块行情",
            "params": ["indicator"],
            "param_defaults": {"indicator": "新浪行业"},
            "cache_ttl": 60,  # 1分钟缓存
            "category": "sector",
        },
        # 雪球数据类
        "stock_individual_basic_info_xq": {
            "description": "雪球个股基本信息",
            "params": ["symbol"],
            "cache_ttl": 3600,
            "category": "info",
        },
        "stock_individual_spot_xq": {
            "description": "雪球个股行情",
            "params": ["symbol"],
            "cache_ttl": 10,
            "category": "realtime",
        },
        # ͬ�бȽ�
        "stock_zh_growth_comparison_em": {
            "description": "东方财富-同业比较-成长性对比",
            "params": ["symbol"],
            "param_defaults": {"symbol": "SZ000895"},
            "cache_ttl": 3600,
            "category": "fundamental",
        },
        "stock_zh_valuation_comparison_em": {
            "description": "东方财富-同业比较-估值对比",
            "params": ["symbol"],
            "param_defaults": {"symbol": "SZ000895"},
            "cache_ttl": 3600,
            "category": "fundamental",
        },
        "stock_zh_dupont_comparison_em": {
            "description": "东方财富-同业比较-杜邦分析对比",
            "params": ["symbol"],
            "param_defaults": {"symbol": "SZ000895"},
            "cache_ttl": 3600,
            "category": "fundamental",
        },
        "stock_zh_scale_comparison_em": {
            "description": "东方财富-同业比较-公司规模对比",
            "params": ["symbol"],
            "param_defaults": {"symbol": "SZ000895"},
            "cache_ttl": 3600,
            "category": "fundamental",
        },
        # 港股行业对比
        "stock_hk_growth_comparison_em": {
            "description": "东方财富-行业对比-成长性对比",
            "params": ["symbol"],
            "param_defaults": {"symbol": "03900"},
            "cache_ttl": 3600,
            "category": "fundamental",
        },
        "stock_hk_valuation_comparison_em": {
            "description": "东方财富-行业对比-估值对比",
            "params": ["symbol"],
            "param_defaults": {"symbol": "03900"},
            "cache_ttl": 3600,
            "category": "fundamental",
        },
        "stock_hk_scale_comparison_em": {
            "description": "东方财富-行业对比-规模对比",
            "params": ["symbol"],
            "param_defaults": {"symbol": "03900"},
            "cache_ttl": 3600,
            "category": "fundamental",
        },
    }

    _CATALOG_LOADED = False
    _CATALOG_PATH = Path(__file__).resolve().parent / "data" / "api_catalog.json"

    # 路径映射（兼容旧版本）
    PATH_ALIASES = {
        # 标准路径映射
        "/api/akshare/": "",  # 移除前缀
        # 兼容旧路径（已废弃）
        "/eastmoney/realtime": "stock_zh_a_spot_em",
        "/eastmoney/kline": "stock_zh_a_hist",
        "/eastmoney/test": "_health_check",
        "fund_em_hk_rank": "fund_hk_rank_em",
        "stock_zh_a_tick_163": "stock_zh_a_tick_tx_js",
        "stock_zh_a_tick_tx": "stock_zh_a_tick_tx_js",
    }

    @classmethod
    def _ensure_catalog_loaded(cls) -> None:
        if not cls._CATALOG_LOADED:
            cls._load_catalog()

    @classmethod
    def _load_catalog(cls) -> None:
        if cls._CATALOG_LOADED:
            return
        try:
            raw = cls._CATALOG_PATH.read_text(encoding="utf-8")
        except FileNotFoundError:
            logger.warning(f"AkShare API catalog file not found: {cls._CATALOG_PATH}")
            cls._CATALOG_LOADED = True
            return
        except Exception as exc:
            logger.error(f"Failed to read AkShare API catalog: {exc}")
            cls._CATALOG_LOADED = True
            return

        try:
            catalog = json.loads(raw)
        except Exception as exc:
            logger.error(f"Failed to parse AkShare API catalog: {exc}")
            cls._CATALOG_LOADED = True
            return

        added = 0
        for entry in catalog.get("apis", []):
            name = entry.get("name")
            if not name or name in cls.API_FUNCTIONS:
                continue

            params = entry.get("params") or []
            param_defaults = entry.get("param_defaults") or {}
            category = cls._normalize_category(entry.get("category"))

            info = {
                "description": entry.get("description") or f"AkShare API {name}",
                "params": params,
                "category": category,
                "cache_ttl": cls._infer_cache_ttl(name, category),
            }

            if param_defaults:
                info["param_defaults"] = param_defaults

            cls.API_FUNCTIONS[name] = info
            added += 1

        # ensure alias entries exist
        for alias, target in cls.PATH_ALIASES.items():
            if not alias or alias.startswith("/") or not target:
                continue
            if alias in cls.API_FUNCTIONS:
                continue
            target_info = cls.API_FUNCTIONS.get(target)
            if not target_info:
                continue
            alias_info = dict(target_info)
            alias_info.setdefault("alias_of", target)
            cls.API_FUNCTIONS[alias] = alias_info

        cls._CATALOG_LOADED = True
        if added:
            logger.debug(
                f"AkShare catalog loaded: added {added} APIs (total {len(cls.API_FUNCTIONS)})"
            )

    @staticmethod
    def _normalize_category(category: Optional[str]) -> str:
        if not category:
            return "misc"
        return str(category).lower()

    @staticmethod
    def _infer_cache_ttl(api_name: str, category: str) -> int:
        name_lower = api_name.lower()
        if any(keyword in name_lower for keyword in ("spot", "realtime", "quote", "bid", "ask")):
            return 10
        if any(keyword in name_lower for keyword in ("intraday", "minute", "min", "tick")):
            return 60
        if any(
            keyword in name_lower
            for keyword in ("hist", "history", "daily", "weekly", "monthly", "kline")
        ):
            return 3600
        if category in {"macro", "article"}:
            return 3600
        if category in {"fund", "bond", "futures", "options", "forex", "crypto", "index"}:
            return 600
        return 300

    @classmethod
    def get_all_api_names(cls) -> list:
        cls._ensure_catalog_loaded()
        return list(cls.API_FUNCTIONS.keys())

    @classmethod
    def normalize_path(cls, path: str) -> str:
        """
        标准化API路径

        Args:
            path: 原始路径

        Returns:
            标准化后的函数名
        """
        cls._ensure_catalog_loaded()

        # 移除开头的斜杠
        path = path.lstrip("/")

        # 检查路径别名
        for alias, target in cls.PATH_ALIASES.items():
            if path.startswith(alias.lstrip("/")):
                if target:
                    return target
                else:
                    # 移除前缀
                    path = path[len(alias.lstrip("/")) :]
                    break

        # 检查是否是有效的API函数
        if path in cls.API_FUNCTIONS:
            return path

        # 尝试移除 /api/akshare/ 前缀
        if path.startswith("api/akshare/"):
            return path[len("api/akshare/") :]

        return path

    @classmethod
    def get_api_info(cls, function_name: str) -> Optional[Dict[str, Any]]:
        """获取API信息"""
        cls._ensure_catalog_loaded()
        api_info = cls.API_FUNCTIONS.get(function_name)
        if api_info:
            return api_info

        alias_target = cls.PATH_ALIASES.get(function_name)
        if alias_target:
            return cls.API_FUNCTIONS.get(alias_target)

        return None

    @classmethod
    def transform_params(cls, function_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        转换参数格式

        Args:
            function_name: 函数名
            params: 原始参数

        Returns:
            转换后的参数
        """
        api_info = cls.get_api_info(function_name)
        if not api_info:
            return params

        # 应用默认值
        if "param_defaults" in api_info:
            for key, default_value in api_info["param_defaults"].items():
                if key not in params or params[key] is None:
                    params[key] = default_value

        # 应用参数转换
        if "param_transform" in api_info:
            for key, transform_func in api_info["param_transform"].items():
                if key in params and params[key] is not None:
                    params[key] = transform_func(params[key])

        # 处理参数别名
        # start -> start_date, end -> end_date
        if "start" in params and "start_date" not in params:
            params["start_date"] = params.pop("start")
        if "end" in params and "end_date" not in params:
            params["end_date"] = params.pop("end")

        return params

    @classmethod
    def validate_params(cls, function_name: str, params: Dict[str, Any]) -> bool:
        """
        验证参数是否完整

        Args:
            function_name: 函数名
            params: 参数字典

        Returns:
            是否有效
        """
        api_info = cls.get_api_info(function_name)
        if not api_info:
            logger.warning(f"未知的API函数: {function_name}")
            return False

        required_params = api_info.get("params", [])

        # 如果没有必需参数，则有效
        if not required_params:
            return True

        # 获取默认值
        defaults = api_info.get("param_defaults", {})

        # 检查必需参数（排除有默认值的）
        for param in required_params:
            # 如果参数有默认值，则是可选的
            if param in defaults:
                continue
            # 检查参数是否存在且不为空
            if param not in params or params[param] is None:
                logger.debug(f"缺少必需参数: {param} for {function_name}")
                return False

        return True

    @classmethod
    def get_cache_ttl(cls, function_name: str) -> int:
        """
        获取缓存TTL

        Args:
            function_name: 函数名

        Returns:
            缓存时间（秒）
        """
        api_info = cls.get_api_info(function_name)
        return api_info.get("cache_ttl", 300) if api_info else 300

    @classmethod
    def get_category(cls, function_name: str) -> str:
        """
        获取API分类

        Args:
            function_name: 函数名

        Returns:
            分类名称
        """
        api_info = cls.get_api_info(function_name)
        return api_info.get("category", "unknown") if api_info else "unknown"

    @classmethod
    def list_apis_by_category(cls, category: str) -> list:
        """
        按分类列出API

        Args:
            category: 分类名称

        Returns:
            API函数名列表
        """
        return [
            name for name, info in cls.API_FUNCTIONS.items() if info.get("category") == category
        ]

    @classmethod
    def is_deprecated_path(cls, path: str) -> bool:
        """
        检查是否是废弃的路径

        Args:
            path: 路径

        Returns:
            是否废弃
        """
        deprecated_prefixes = ["/eastmoney/", "/east_money/", "/em/"]
        return any(path.startswith(prefix) for prefix in deprecated_prefixes)
