"""
错误模式分析器

分析数据源错误模式，提供根因分析和修复建议
"""

import difflib
import json
import re
import time
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from threading import Lock
from typing import Any, DefaultDict, Dict, List, Optional, Set, TypedDict

from core.observability.logging.monitoring_logger import ErrorInfo, ErrorType
from loguru import logger


class ErrorStats(TypedDict):
    total_errors: int
    by_type: DefaultDict[str, int]
    by_source: DefaultDict[str, int]
    by_pattern: DefaultDict[str, int]
    recurring_errors: DefaultDict[str, int]


@dataclass
class ErrorPattern:
    """错误模式"""

    pattern_id: str
    error_type: ErrorType
    pattern_regex: str
    description: str
    root_cause: str
    solution: str
    severity: str  # "low", "medium", "high", "critical"
    auto_recoverable: bool = False
    retry_strategy: Optional[str] = None


@dataclass
class ErrorCluster:
    """错误聚类"""

    cluster_id: str
    error_type: ErrorType
    error_messages: List[str]
    count: int
    first_seen: float
    last_seen: float
    affected_sources: Set[str]
    common_pattern: Optional[str] = None
    suggested_fix: Optional[str] = None


@dataclass
class RootCauseAnalysis:
    """根因分析结果"""

    error_id: str
    timestamp: float
    error_chain: List[str]  # 错误传播链
    root_cause: str
    impact_scope: List[str]  # 影响范围
    remediation_steps: List[str]  # 修复步骤
    prevention_measures: List[str]  # 预防措施


class ErrorAnalyzer:
    """错误分析器"""

    def __init__(self) -> None:
        # 错误模式库
        self.error_patterns: List[ErrorPattern] = self._init_error_patterns()

        # 错误历史
        self.error_history: List[Dict[str, Any]] = []
        self.max_history_size = 10000

        # 错误聚类
        self.error_clusters: Dict[str, ErrorCluster] = {}

        # 错误统计
        self.error_stats: ErrorStats = {
            "total_errors": 0,
            "by_type": defaultdict(int),
            "by_source": defaultdict(int),
            "by_pattern": defaultdict(int),
            "recurring_errors": defaultdict(int),
        }

        # 根因分析缓存
        self.rca_cache: Dict[str, RootCauseAnalysis] = {}

        # 修复建议库
        self.fix_suggestions: Dict[str, List[str]] = self._init_fix_suggestions()

        # 线程锁
        self.lock = Lock()

        # 导出路径
        self.export_dir = Path("data/monitoring/exports")
        self.export_dir.mkdir(parents=True, exist_ok=True)

        logger.info("错误分析器初始化完成")

    def _init_error_patterns(self) -> List[ErrorPattern]:
        """初始化错误模式库"""
        patterns = [
            # 网络错误
            ErrorPattern(
                pattern_id="NET_001",
                error_type=ErrorType.NETWORK_ERROR,
                pattern_regex=r".*Connection refused.*",
                description="连接被拒绝",
                root_cause="目标服务器拒绝连接，可能是服务未启动或防火墙阻止",
                solution="1. 检查目标服务是否正常运行\n2. 检查防火墙设置\n3. 验证网络连通性",
                severity="high",
                auto_recoverable=True,
                retry_strategy="exponential_backoff",
            ),
            ErrorPattern(
                pattern_id="NET_002",
                error_type=ErrorType.TIMEOUT_ERROR,
                pattern_regex=r".*timeout.*|.*timed out.*",
                description="请求超时",
                root_cause="网络延迟高或服务器响应慢",
                solution="1. 增加超时时间\n2. 检查网络质量\n3. 优化请求参数减少数据量",
                severity="medium",
                auto_recoverable=True,
                retry_strategy="linear_backoff",
            ),
            ErrorPattern(
                pattern_id="NET_003",
                error_type=ErrorType.CONNECTION_ERROR,
                pattern_regex=r".*Connection reset.*",
                description="连接被重置",
                root_cause="服务器主动断开连接，可能是负载过高",
                solution="1. 实现连接池管理\n2. 添加重连机制\n3. 降低请求频率",
                severity="medium",
                auto_recoverable=True,
                retry_strategy="immediate_retry",
            ),
            # 认证错误
            ErrorPattern(
                pattern_id="AUTH_001",
                error_type=ErrorType.AUTH_ERROR,
                pattern_regex=r".*401.*|.*Unauthorized.*",
                description="认证失败",
                root_cause="认证凭据无效或已过期",
                solution="1. 检查API密钥是否正确\n2. 刷新认证令牌\n3. 验证认证配置",
                severity="critical",
                auto_recoverable=False,
            ),
            ErrorPattern(
                pattern_id="AUTH_002",
                error_type=ErrorType.AUTH_ERROR,
                pattern_regex=r".*403.*|.*Forbidden.*",
                description="权限不足",
                root_cause="当前账户没有访问该资源的权限",
                solution="1. 检查账户权限设置\n2. 联系管理员开通权限\n3. 使用正确的API端点",
                severity="high",
                auto_recoverable=False,
            ),
            # 限流错误
            ErrorPattern(
                pattern_id="RATE_001",
                error_type=ErrorType.RATE_LIMIT_ERROR,
                pattern_regex=r".*429.*|.*rate limit.*|.*too many requests.*",
                description="请求频率超限",
                root_cause="超过API调用频率限制",
                solution="1. 降低请求频率\n2. 实现请求队列和限流\n3. 使用批量API减少请求次数",
                severity="medium",
                auto_recoverable=True,
                retry_strategy="exponential_backoff",
            ),
            # 数据错误
            ErrorPattern(
                pattern_id="DATA_001",
                error_type=ErrorType.PARSE_ERROR,
                pattern_regex=r".*JSON.*|.*parse.*|.*decode.*",
                description="数据解析失败",
                root_cause="返回数据格式不符合预期",
                solution="1. 检查API响应格式是否变更\n2. 添加数据格式验证\n3. 实现容错解析逻辑",
                severity="high",
                auto_recoverable=False,
            ),
            ErrorPattern(
                pattern_id="DATA_002",
                error_type=ErrorType.VALIDATION_ERROR,
                pattern_regex=r".*validation.*|.*invalid.*parameter.*",
                description="参数验证失败",
                root_cause="请求参数不符合API要求",
                solution="1. 检查参数格式和类型\n2. 验证必填参数是否完整\n3. 参考API文档更新参数",
                severity="low",
                auto_recoverable=False,
            ),
            # 服务错误
            ErrorPattern(
                pattern_id="SVC_001",
                error_type=ErrorType.UNKNOWN_ERROR,
                pattern_regex=r".*500.*|.*Internal Server Error.*",
                description="服务器内部错误",
                root_cause="服务器端发生未知错误",
                solution="1. 等待服务恢复\n2. 切换到备用数据源\n3. 联系服务提供商",
                severity="critical",
                auto_recoverable=True,
                retry_strategy="exponential_backoff",
            ),
            ErrorPattern(
                pattern_id="SVC_002",
                error_type=ErrorType.UNKNOWN_ERROR,
                pattern_regex=r".*503.*|.*Service Unavailable.*",
                description="服务暂时不可用",
                root_cause="服务器维护或过载",
                solution="1. 等待服务恢复\n2. 启用故障转移\n3. 使用缓存数据",
                severity="high",
                auto_recoverable=True,
                retry_strategy="exponential_backoff",
            ),
        ]

        return patterns

    def _init_fix_suggestions(self) -> Dict[str, List[str]]:
        """初始化修复建议库"""
        return {
            ErrorType.NETWORK_ERROR.value: [
                "检查网络连接状态",
                "验证目标服务器是否可访问",
                "增加连接重试机制",
                "实现连接池管理",
                "配置合理的超时时间",
            ],
            ErrorType.TIMEOUT_ERROR.value: [
                "增加超时时间配置",
                "优化请求数据量",
                "使用分页或批量请求",
                "检查服务器负载",
                "实现请求缓存",
            ],
            ErrorType.AUTH_ERROR.value: [
                "验证API密钥配置",
                "检查认证令牌是否过期",
                "确认账户权限设置",
                "更新认证方式",
                "联系服务提供商",
            ],
            ErrorType.RATE_LIMIT_ERROR.value: [
                "实现请求限流",
                "使用请求队列",
                "批量合并请求",
                "增加请求间隔",
                "升级API配额",
            ],
            ErrorType.DATA_ERROR.value: [
                "验证数据格式",
                "添加数据校验",
                "实现容错处理",
                "更新数据模型",
                "检查API版本",
            ],
        }

    def analyze_error(
        self,
        error_info: ErrorInfo,
        source_type: str,
        metadata: Dict[str, Any],
    ) -> Dict[str, Any]:
        """分析单个错误"""
        with self.lock:
            # 更新统计
            self.error_stats["total_errors"] += 1
            self.error_stats["by_type"][error_info.error_type.value] += 1
            self.error_stats["by_source"][source_type] += 1

            # 记录错误历史
            error_record: Dict[str, Any] = {
                "timestamp": time.time(),
                "source_type": source_type,
                "error_type": error_info.error_type.value,
                "error_message": error_info.error_message,
                "metadata": metadata,
            }

            self.error_history.append(error_record)
            if len(self.error_history) > self.max_history_size:
                self.error_history.pop(0)

            # 模式匹配
            matched_pattern = self._match_pattern(error_info)
            if matched_pattern:
                self.error_stats["by_pattern"][matched_pattern.pattern_id] += 1
                error_record["pattern"] = matched_pattern.pattern_id
                error_record["solution"] = matched_pattern.solution

            # 错误聚类
            self._cluster_error(error_info, source_type)

            # 根因分析
            rca = self._perform_root_cause_analysis(error_info, source_type, metadata)
            if rca:
                error_record["root_cause"] = rca.root_cause
                error_record["remediation"] = rca.remediation_steps

            return error_record

    def _match_pattern(self, error_info: ErrorInfo) -> Optional[ErrorPattern]:
        """匹配错误模式"""
        error_message = error_info.error_message or ""

        for pattern in self.error_patterns:
            if pattern.error_type == error_info.error_type:
                if re.search(pattern.pattern_regex, error_message, re.IGNORECASE):
                    return pattern

        return None

    def _cluster_error(self, error_info: ErrorInfo, source_type: str) -> None:
        """错误聚类"""
        error_message = error_info.error_message or ""

        # 查找相似的错误集群
        best_cluster: Optional[ErrorCluster] = None
        best_similarity: float = 0.0

        for cluster in self.error_clusters.values():
            if cluster.error_type == error_info.error_type:
                # 计算相似度
                similarity = self._calculate_similarity(error_message, cluster.error_messages)

                if similarity > 0.7 and similarity > best_similarity:
                    best_cluster = cluster
                    best_similarity = similarity

        if best_cluster:
            # 添加到现有集群
            best_cluster.error_messages.append(error_message)
            best_cluster.count += 1
            best_cluster.last_seen = time.time()
            best_cluster.affected_sources.add(source_type)
        else:
            # 创建新集群
            cluster_id = f"cluster_{len(self.error_clusters)}"
            new_cluster = ErrorCluster(
                cluster_id=cluster_id,
                error_type=error_info.error_type,
                error_messages=[error_message],
                count=1,
                first_seen=time.time(),
                last_seen=time.time(),
                affected_sources={source_type},
            )
            self.error_clusters[cluster_id] = new_cluster

    def _calculate_similarity(self, message: str, messages: List[str]) -> float:
        """计算错误消息相似度"""
        if not messages:
            return 0.0

        # 使用difflib计算相似度
        similarities = [
            difflib.SequenceMatcher(None, message, msg).ratio()
            for msg in messages[-10:]  # 只比较最近的10条
        ]

        return max(similarities)

    def _perform_root_cause_analysis(
        self,
        error_info: ErrorInfo,
        source_type: str,
        metadata: Dict[str, Any],
    ) -> Optional[RootCauseAnalysis]:
        """执行根因分析"""
        error_id = f"rca_{time.time()}"

        # 分析错误链
        error_chain = []
        if error_info.stack_trace:
            # 从堆栈中提取关键信息
            lines = error_info.stack_trace.split("\n")
            for line in lines:
                if "File" in line and ".py" in line:
                    error_chain.append(line.strip())

        # 确定根因
        root_cause = "未知原因"
        remediation_steps = []
        prevention_measures = []

        # 基于错误类型分析
        if error_info.error_type == ErrorType.NETWORK_ERROR:
            root_cause = "网络连接问题"
            remediation_steps = ["检查网络连接", "验证目标服务状态", "实施重试机制"]
            prevention_measures = ["添加健康检查", "实现熔断器模式", "配置备用数据源"]
        elif error_info.error_type == ErrorType.AUTH_ERROR:
            root_cause = "认证配置错误"
            remediation_steps = ["检查认证凭据", "更新API密钥", "验证权限设置"]
            prevention_measures = ["实现凭据轮换", "添加认证监控", "配置认证缓存"]
        elif error_info.error_type == ErrorType.RATE_LIMIT_ERROR:
            root_cause = "请求频率过高"
            remediation_steps = ["降低请求频率", "实现请求队列", "使用批量API"]
            prevention_measures = ["配置限流器", "监控API配额", "优化请求策略"]

        rca = RootCauseAnalysis(
            error_id=error_id,
            timestamp=time.time(),
            error_chain=error_chain,
            root_cause=root_cause,
            impact_scope=[source_type],
            remediation_steps=remediation_steps,
            prevention_measures=prevention_measures,
        )

        # 缓存分析结果
        self.rca_cache[error_id] = rca

        return rca

    def get_error_patterns_report(self) -> Dict:
        """获取错误模式报告"""
        with self.lock:
            # 统计最常见的错误模式
            top_patterns = sorted(
                self.error_stats["by_pattern"].items(), key=lambda x: x[1], reverse=True
            )[:10]

            # 获取活跃的错误集群
            active_clusters = [
                {
                    "cluster_id": cluster.cluster_id,
                    "error_type": cluster.error_type.value,
                    "count": cluster.count,
                    "affected_sources": list(cluster.affected_sources),
                    "last_seen": datetime.fromtimestamp(cluster.last_seen).isoformat(),
                }
                for cluster in self.error_clusters.values()
                if time.time() - cluster.last_seen < 3600  # 最近1小时
            ]

            return {
                "total_errors": self.error_stats["total_errors"],
                "by_type": dict(self.error_stats["by_type"]),
                "by_source": dict(self.error_stats["by_source"]),
                "top_patterns": [
                    {
                        "pattern_id": pid,
                        "count": count,
                        "pattern": next(
                            (p for p in self.error_patterns if p.pattern_id == pid), None
                        ),
                    }
                    for pid, count in top_patterns
                ],
                "active_clusters": active_clusters,
            }

    def get_remediation_suggestions(self, error_type: str) -> List[str]:
        """获取修复建议"""
        return self.fix_suggestions.get(error_type, ["请查看详细错误日志"])

    def export_analysis(self) -> None:
        """导出分析结果"""
        try:
            # 导出错误模式分析
            patterns_file = self.export_dir / "error_patterns.json"
            with open(patterns_file, "w", encoding="utf-8") as f:
                export_data = {
                    "timestamp": time.time(),
                    "datetime": datetime.now().isoformat(),
                    "report": self.get_error_patterns_report(),
                    "recent_errors": self.error_history[-100:],  # 最近100个错误
                    "remediation_guide": self.fix_suggestions,
                }
                json.dump(export_data, f, ensure_ascii=False, indent=2, default=str)

            logger.debug("错误分析结果导出成功")

        except Exception as e:
            logger.error(f"导出错误分析失败: {e}")


# 全局实例
error_analyzer = ErrorAnalyzer()


def get_error_analyzer() -> ErrorAnalyzer:
    """获取错误分析器实例"""
    return error_analyzer
