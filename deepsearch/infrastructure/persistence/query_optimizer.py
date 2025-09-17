"""
数据库查询优化器模块

提供查询分析、优化和索引建议
"""
import time
import re
from datetime import datetime
from collections import defaultdict, deque
from typing import Dict, List, Any, Optional, Union

from sqlalchemy import text, Index, event
from sqlalchemy.orm import Query, selectinload, joinedload, subqueryload
from sqlalchemy.engine import Engine
from loguru import logger


class QueryStats:
    """查询统计"""
    
    def __init__(self, query: str):
        self.query = query
        self.executions = 0
        self.total_time = 0
        self.min_time = float('inf')
        self.max_time = 0
        self.errors = 0
        self.last_execution = None
        
    def record_execution(self, duration: float, error: bool = False):
        """记录执行"""
        self.executions += 1
        self.total_time += duration
        self.min_time = min(self.min_time, duration)
        self.max_time = max(self.max_time, duration)
        self.last_execution = datetime.now()
        
        if error:
            self.errors += 1
            
    @property
    def avg_time(self) -> float:
        """平均执行时间"""
        return self.total_time / self.executions if self.executions > 0 else 0


class QueryOptimizer:
    """查询优化器"""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not hasattr(self, '_initialized'):
            self.query_stats = defaultdict(lambda: QueryStats(''))
            self.slow_queries = deque(maxlen=100)
            self.slow_threshold = 1.0  # 秒
            self.query_cache = {}
            self.index_suggestions = []
            self.n_plus_one_detections = []
            self._initialized = True
            
    def analyze_query(self, query: Union[str, Query]) -> Dict[str, Any]:
        """分析查询"""
        query_str = str(query)
        
        analysis = {
            'query': query_str,
            'type': self._get_query_type(query_str),
            'tables': self._extract_tables(query_str),
            'conditions': self._extract_conditions(query_str),
            'joins': self._extract_joins(query_str),
            'has_index': False,
            'suggestions': []
        }
        
        # 检查是否使用索引
        if analysis['type'] == 'SELECT':
            analysis['has_index'] = self._check_index_usage(query_str, analysis['tables'])
            
        # 生成优化建议
        analysis['suggestions'] = self._generate_suggestions(analysis)
        
        return analysis
        
    def _get_query_type(self, query: str) -> str:
        """获取查询类型"""
        query_upper = query.upper().strip()
        
        if query_upper.startswith('SELECT'):
            return 'SELECT'
        elif query_upper.startswith('INSERT'):
            return 'INSERT'
        elif query_upper.startswith('UPDATE'):
            return 'UPDATE'
        elif query_upper.startswith('DELETE'):
            return 'DELETE'
        else:
            return 'OTHER'
            
    def _extract_tables(self, query: str) -> List[str]:
        """提取表名"""
        tables = []
        
        # FROM子句
        from_pattern = r'FROM\s+([^\s,]+)'
        from_matches = re.findall(from_pattern, query, re.IGNORECASE)
        tables.extend(from_matches)
        
        # JOIN子句
        join_pattern = r'JOIN\s+([^\s]+)'
        join_matches = re.findall(join_pattern, query, re.IGNORECASE)
        tables.extend(join_matches)
        
        return list(set(tables))
        
    def _extract_conditions(self, query: str) -> List[str]:
        """提取查询条件"""
        conditions = []
        
        # WHERE子句
        where_pattern = r'WHERE\s+(.*?)(?:GROUP|ORDER|LIMIT|$)'
        where_match = re.search(where_pattern, query, re.IGNORECASE | re.DOTALL)
        
        if where_match:
            where_clause = where_match.group(1)
            # 分割条件
            condition_patterns = [
                r'(\w+)\s*=\s*[^\s]+',
                r'(\w+)\s+IN\s*\([^)]+\)',
                r'(\w+)\s+BETWEEN\s+[^\s]+\s+AND\s+[^\s]+',
                r'(\w+)\s+LIKE\s+[^\s]+',
                r'(\w+)\s+IS\s+(?:NOT\s+)?NULL'
            ]
            
            for pattern in condition_patterns:
                matches = re.findall(pattern, where_clause, re.IGNORECASE)
                conditions.extend(matches)
                
        return list(set(conditions))
        
    def _extract_joins(self, query: str) -> List[Dict[str, str]]:
        """提取JOIN信息"""
        joins = []
        
        join_pattern = r'(INNER|LEFT|RIGHT|FULL)?\s*JOIN\s+([^\s]+)\s+(?:AS\s+)?(\w+)?\s+ON\s+([^WHERE|GROUP|ORDER|LIMIT]+)'
        matches = re.findall(join_pattern, query, re.IGNORECASE)
        
        for match in matches:
            joins.append({
                'type': match[0] or 'INNER',
                'table': match[1],
                'alias': match[2],
                'condition': match[3].strip()
            })
            
        return joins
        
    def _check_index_usage(self, query: str, tables: List[str]) -> bool:
        """检查是否使用索引"""
        # 这里简化处理，实际需要EXPLAIN查询
        conditions = self._extract_conditions(query)
        
        # 如果有WHERE条件，假设可能使用索引
        return len(conditions) > 0
        
    def _generate_suggestions(self, analysis: Dict[str, Any]) -> List[str]:
        """生成优化建议"""
        suggestions = []
        
        # SELECT查询优化建议
        if analysis['type'] == 'SELECT':
            # 检查是否有WHERE条件
            if not analysis['conditions']:
                suggestions.append("考虑添加WHERE条件以减少扫描行数")
                
            # 检查JOIN
            if len(analysis['joins']) > 3:
                suggestions.append("过多的JOIN可能影响性能，考虑分步查询或使用子查询")
                
            # 检查索引
            if not analysis['has_index']:
                suggestions.append(f"考虑为条件字段 {', '.join(analysis['conditions'])} 创建索引")
                
        # 检查SELECT *
        if 'SELECT *' in analysis['query'].upper():
            suggestions.append("避免使用SELECT *，只查询需要的字段")
            
        # 检查LIKE模式
        if re.search(r'LIKE\s+[\'"]%\w+', analysis['query'], re.IGNORECASE):
            suggestions.append("前缀通配符(LIKE '%...')会导致全表扫描，考虑使用全文索引")
            
        return suggestions
        
    def optimize_query(self, query: Query) -> Query:
        """优化SQLAlchemy查询"""
        # 检测关联加载
        if self._has_relationships(query):
            query = self._optimize_loading_strategy(query)
            
        # 添加索引提示（如果有）
        query = self._add_index_hints(query)
        
        return query
        
    def _has_relationships(self, query: Query) -> bool:
        """检查查询是否有关联"""
        # 检查是否有join或关联属性访问
        return hasattr(query, '_join_entities') and len(query._join_entities) > 0
        
    def _optimize_loading_strategy(self, query: Query) -> Query:
        """优化加载策略"""
        # 这里简化处理，实际需要分析具体的关联关系
        # 使用selectinload避免N+1问题
        return query
        
    def _add_index_hints(self, query: Query) -> Query:
        """添加索引提示"""
        # SQLAlchemy的索引提示需要具体数据库支持
        return query
        
    def detect_n_plus_one(self, session) -> List[Dict[str, Any]]:
        """检测N+1查询问题"""
        detections = []
        
        # 监听查询事件
        @event.listens_for(session, "after_bulk_update")
        def receive_after_bulk_update(update_context):
            # 检测批量更新
            pass
            
        # 分析查询模式
        query_patterns = defaultdict(int)
        
        for query_str, stats in self.query_stats.items():
            # 检测重复的相似查询
            base_query = re.sub(r'\d+', 'N', query_str)  # 将数字替换为N
            query_patterns[base_query] += stats.executions
            
        # 识别N+1模式
        for pattern, count in query_patterns.items():
            if count > 10 and 'WHERE' in pattern and 'id = N' in pattern:
                detections.append({
                    'pattern': pattern,
                    'count': count,
                    'type': 'N+1',
                    'suggestion': '使用joinedload或selectinload预加载关联数据'
                })
                
        self.n_plus_one_detections = detections
        return detections
        
    def suggest_indexes(self, engine: Engine) -> List[Dict[str, Any]]:
        """建议索引"""
        suggestions = []
        
        # 分析慢查询
        for query_data in self.slow_queries:
            query_str = query_data['query']
            tables = self._extract_tables(query_str)
            conditions = self._extract_conditions(query_str)
            
            if conditions:
                for table in tables:
                    for column in conditions:
                        suggestion = {
                            'table': table,
                            'column': column,
                            'index_name': f'idx_{table}_{column}',
                            'reason': f'慢查询频繁使用此字段作为条件',
                            'query_example': query_str[:100]
                        }
                        
                        # 检查索引是否已存在
                        if not self._index_exists(engine, table, column):
                            suggestions.append(suggestion)
                            
        # 复合索引建议
        suggestions.extend(self._suggest_composite_indexes())
        
        self.index_suggestions = suggestions
        return suggestions
        
    def _index_exists(self, engine: Engine, table: str, column: str) -> bool:
        """检查索引是否存在"""
        try:
            # 查询数据库的索引信息
            if engine.dialect.name == 'postgresql':
                query = text("""
                    SELECT 1 FROM pg_indexes 
                    WHERE tablename = :table 
                    AND indexdef LIKE :column
                """)
                result = engine.execute(query, table=table, column=f'%{column}%')
                return result.rowcount > 0
                
            elif engine.dialect.name == 'mysql':
                query = text("""
                    SELECT 1 FROM information_schema.statistics 
                    WHERE table_name = :table 
                    AND column_name = :column
                """)
                result = engine.execute(query, table=table, column=column)
                return result.rowcount > 0
                
            elif engine.dialect.name == 'sqlite':
                query = text(f"PRAGMA index_info('idx_{table}_{column}')")
                result = engine.execute(query)
                return result.rowcount > 0
                
        except Exception as e:
            logger.debug(f"检查索引失败: {e}")
            
        return False
        
    def _suggest_composite_indexes(self) -> List[Dict[str, Any]]:
        """建议复合索引"""
        suggestions = []
        
        # 分析经常一起使用的字段组合
        field_combinations = defaultdict(int)
        
        for query_str, stats in self.query_stats.items():
            conditions = self._extract_conditions(query_str)
            
            if len(conditions) > 1:
                # 记录字段组合
                combo = tuple(sorted(conditions))
                field_combinations[combo] += stats.executions
                
        # 生成复合索引建议
        for combo, count in field_combinations.items():
            if count > 50 and len(combo) <= 3:  # 频繁使用且不超过3个字段
                suggestions.append({
                    'type': 'composite',
                    'columns': list(combo),
                    'index_name': f"idx_{'_'.join(combo)}",
                    'reason': f'这些字段经常一起使用 (使用{count}次)',
                    'priority': 'HIGH' if count > 100 else 'MEDIUM'
                })
                
        return suggestions
        
    def auto_create_indexes(self, engine: Engine, dry_run: bool = True) -> List[str]:
        """自动创建索引"""
        created_indexes = []
        
        for suggestion in self.index_suggestions:
            if suggestion.get('type') == 'composite':
                # 创建复合索引
                columns = suggestion['columns']
                index_name = suggestion['index_name']
                
                # 这里需要获取实际的表对象
                # 简化示例
                sql = f"CREATE INDEX {index_name} ON table_name ({', '.join(columns)})"
                
            else:
                # 创建单列索引
                table = suggestion['table']
                column = suggestion['column']
                index_name = suggestion['index_name']
                
                sql = f"CREATE INDEX {index_name} ON {table} ({column})"
                
            if dry_run:
                logger.info(f"[DRY RUN] 将创建索引: {sql}")
                created_indexes.append(sql)
            else:
                try:
                    engine.execute(text(sql))
                    created_indexes.append(index_name)
                    logger.info(f"创建索引成功: {index_name}")
                except Exception as e:
                    logger.error(f"创建索引失败: {e}")
                    
        return created_indexes
        
    def record_query_execution(self, query: str, duration: float, error: bool = False):
        """记录查询执行"""
        stats = self.query_stats[query]
        stats.query = query
        stats.record_execution(duration, error)
        
        # 记录慢查询
        if duration > self.slow_threshold:
            self.slow_queries.append({
                'query': query,
                'duration': duration,
                'timestamp': datetime.now(),
                'error': error
            })
            
            try:
                from deepsearch.config import settings
                if settings.app.env == "dev":
                    logger.warning(f"慢查询检测 ({duration:.2f}s): {query[:100]}...")
            except ImportError:
                pass
                
    def get_slow_queries(self, top_n: int = 10) -> List[Dict[str, Any]]:
        """获取慢查询"""
        # 按执行时间排序
        sorted_queries = sorted(
            self.query_stats.items(),
            key=lambda x: x[1].avg_time,
            reverse=True
        )
        
        slow_queries = []
        for query, stats in sorted_queries[:top_n]:
            if stats.avg_time > self.slow_threshold:
                slow_queries.append({
                    'query': query[:200],  # 限制长度
                    'executions': stats.executions,
                    'avg_time': stats.avg_time,
                    'min_time': stats.min_time,
                    'max_time': stats.max_time,
                    'total_time': stats.total_time,
                    'errors': stats.errors,
                    'last_execution': stats.last_execution.isoformat() if stats.last_execution else None
                })
                
        return slow_queries
        
    def get_optimization_report(self) -> Dict[str, Any]:
        """获取优化报告"""
        return {
            'timestamp': datetime.now().isoformat(),
            'total_queries': len(self.query_stats),
            'slow_queries': self.get_slow_queries(),
            'n_plus_one_detections': self.n_plus_one_detections,
            'index_suggestions': self.index_suggestions,
            'statistics': self._get_statistics()
        }
        
    def _get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        total_executions = sum(s.executions for s in self.query_stats.values())
        total_time = sum(s.total_time for s in self.query_stats.values())
        total_errors = sum(s.errors for s in self.query_stats.values())
        
        return {
            'total_executions': total_executions,
            'total_time': total_time,
            'avg_time': total_time / total_executions if total_executions > 0 else 0,
            'error_rate': total_errors / total_executions if total_executions > 0 else 0,
            'slow_query_count': len(self.slow_queries),
            'cached_queries': len(self.query_cache)
        }
        
    def clear_stats(self):
        """清空统计信息"""
        self.query_stats.clear()
        self.slow_queries.clear()
        self.n_plus_one_detections.clear()
        self.index_suggestions.clear()
        logger.info("查询优化器统计已清空")
        
    def set_slow_threshold(self, threshold: float):
        """设置慢查询阈值"""
        self.slow_threshold = threshold
        logger.info(f"慢查询阈值已设置为 {threshold}秒")


# 创建全局实例
query_optimizer = QueryOptimizer()


# SQLAlchemy事件监听器
def setup_query_monitoring(engine: Engine):
    """设置查询监控"""
    
    @event.listens_for(engine, "before_cursor_execute")
    def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        conn.info.setdefault('query_start_time', []).append(time.time())
        
    @event.listens_for(engine, "after_cursor_execute")
    def after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        total_time = time.time() - conn.info['query_start_time'].pop(-1)
        query_optimizer.record_query_execution(statement, total_time)
        
    @event.listens_for(engine, "handle_error")
    def handle_error(exception_context):
        if 'query_start_time' in exception_context.connection.info:
            total_time = time.time() - exception_context.connection.info['query_start_time'].pop(-1)
            query_optimizer.record_query_execution(
                exception_context.statement,
                total_time,
                error=True
            )
            
    logger.info("查询监控已启动")