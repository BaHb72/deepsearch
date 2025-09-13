"""
日志分析工具

用于分析日志文件，生成报告和统计信息
"""
import re
import json
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from collections import defaultdict, Counter
import click


class LogAnalyzer:
    """日志分析器"""
    
    def __init__(self, log_dir: str = "./logs"):
        """
        初始化分析器
        
        Args:
            log_dir: 日志目录路径
        """
        self.log_dir = Path(log_dir)
        self.patterns = {
            'timestamp': r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{3})',
            'level': r'\| (TRACE|DEBUG|INFO|WARNING|ERROR|CRITICAL) \|',
            'component': r'component=(\w+)',
            'duration_ms': r'duration_ms=(\d+)',
            'error_type': r'error_type=(\w+)',
            'status_code': r'status=(\d+)',
        }
    
    def analyze_errors(self, hours: int = 24) -> Dict[str, Any]:
        """
        分析错误日志
        
        Args:
            hours: 分析时间范围（小时）
            
        Returns:
            错误分析报告
        """
        cutoff_time = datetime.now() - timedelta(hours=hours)
        errors = []
        
        # 遍历错误日志文件
        error_dir = self.log_dir / "error"
        if error_dir.exists():
            for log_file in error_dir.glob("*.log"):
                errors.extend(self._parse_log_file(log_file, cutoff_time, ["ERROR", "CRITICAL"]))
        
        # 分析错误模式
        error_types = Counter(e.get('error_type', 'unknown') for e in errors)
        error_components = Counter(e.get('component', 'unknown') for e in errors)
        
        # 错误趋势（按小时）
        hourly_errors = defaultdict(int)
        for error in errors:
            if 'timestamp' in error:
                hour_key = error['timestamp'].strftime('%Y-%m-%d %H:00')
                hourly_errors[hour_key] += 1
        
        return {
            'total_errors': len(errors),
            'time_range_hours': hours,
            'top_error_types': dict(error_types.most_common(10)),
            'top_error_components': dict(error_components.most_common(10)),
            'hourly_trend': dict(sorted(hourly_errors.items())),
            'recent_errors': errors[-10:],  # 最近10条错误
        }
    
    def analyze_performance(self, hours: int = 24) -> Dict[str, Any]:
        """
        分析性能日志
        
        Args:
            hours: 分析时间范围（小时）
            
        Returns:
            性能分析报告
        """
        cutoff_time = datetime.now() - timedelta(hours=hours)
        perf_logs = []
        
        # 遍历性能日志文件
        perf_dir = self.log_dir / "performance"
        if perf_dir.exists():
            for log_file in perf_dir.glob("*.log"):
                perf_logs.extend(self._parse_log_file(log_file, cutoff_time))
        
        # 提取耗时信息
        durations = []
        slow_operations = []
        
        for log in perf_logs:
            if 'duration_ms' in log:
                duration = log['duration_ms']
                durations.append(duration)
                
                if duration > 1000:  # 超过1秒的慢操作
                    slow_operations.append({
                        'operation': log.get('message', ''),
                        'duration_ms': duration,
                        'timestamp': log.get('timestamp'),
                        'component': log.get('component'),
                    })
        
        # 计算统计信息
        if durations:
            durations.sort()
            percentiles = {
                'p50': durations[len(durations) // 2],
                'p90': durations[int(len(durations) * 0.9)],
                'p95': durations[int(len(durations) * 0.95)],
                'p99': durations[int(len(durations) * 0.99)],
            }
        else:
            percentiles = {}
        
        return {
            'total_operations': len(durations),
            'slow_operations_count': len(slow_operations),
            'percentiles': percentiles,
            'avg_duration_ms': sum(durations) / len(durations) if durations else 0,
            'max_duration_ms': max(durations) if durations else 0,
            'top_slow_operations': sorted(slow_operations, key=lambda x: x['duration_ms'], reverse=True)[:10],
        }
    
    def analyze_components(self, hours: int = 24) -> Dict[str, Any]:
        """
        分析组件日志
        
        Args:
            hours: 分析时间范围（小时）
            
        Returns:
            组件分析报告
        """
        cutoff_time = datetime.now() - timedelta(hours=hours)
        component_logs = defaultdict(list)
        
        # 遍历所有日志文件
        for category_dir in self.log_dir.iterdir():
            if category_dir.is_dir():
                for log_file in category_dir.glob("*.log"):
                    logs = self._parse_log_file(log_file, cutoff_time)
                    for log in logs:
                        component = log.get('component', 'unknown')
                        component_logs[component].append(log)
        
        # 统计每个组件的日志
        component_stats = {}
        for component, logs in component_logs.items():
            level_counts = Counter(log.get('level', 'UNKNOWN') for log in logs)
            
            component_stats[component] = {
                'total_logs': len(logs),
                'level_distribution': dict(level_counts),
                'error_rate': level_counts.get('ERROR', 0) / len(logs) if logs else 0,
                'warning_rate': level_counts.get('WARNING', 0) / len(logs) if logs else 0,
            }
        
        return {
            'component_count': len(component_stats),
            'component_stats': component_stats,
            'most_active': sorted(component_stats.items(), 
                                 key=lambda x: x[1]['total_logs'], 
                                 reverse=True)[:10],
            'highest_error_rate': sorted(component_stats.items(),
                                        key=lambda x: x[1]['error_rate'],
                                        reverse=True)[:10],
        }
    
    def _parse_log_file(self, file_path: Path, cutoff_time: datetime, 
                       levels: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """解析日志文件"""
        logs = []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                for line in f:
                    log_entry = self._parse_log_line(line)
                    
                    if log_entry:
                        # 检查时间范围
                        if 'timestamp' in log_entry and log_entry['timestamp'] < cutoff_time:
                            continue
                        
                        # 检查日志级别
                        if levels and log_entry.get('level') not in levels:
                            continue
                        
                        logs.append(log_entry)
                        
        except Exception as e:
            print(f"Error parsing {file_path}: {e}")
        
        return logs
    
    def _parse_log_line(self, line: str) -> Optional[Dict[str, Any]]:
        """解析单行日志"""
        log_entry = {'raw': line.strip()}
        
        # 提取时间戳
        timestamp_match = re.search(self.patterns['timestamp'], line)
        if timestamp_match:
            try:
                log_entry['timestamp'] = datetime.strptime(
                    timestamp_match.group(1), 
                    '%Y-%m-%d %H:%M:%S.%f'
                )
            except:
                pass
        
        # 提取日志级别
        level_match = re.search(self.patterns['level'], line)
        if level_match:
            log_entry['level'] = level_match.group(1)
        
        # 提取组件
        component_match = re.search(self.patterns['component'], line)
        if component_match:
            log_entry['component'] = component_match.group(1)
        
        # 提取耗时
        duration_match = re.search(self.patterns['duration_ms'], line)
        if duration_match:
            log_entry['duration_ms'] = int(duration_match.group(1))
        
        # 提取错误类型
        error_type_match = re.search(self.patterns['error_type'], line)
        if error_type_match:
            log_entry['error_type'] = error_type_match.group(1)
        
        # 提取状态码
        status_match = re.search(self.patterns['status_code'], line)
        if status_match:
            log_entry['status_code'] = int(status_match.group(1))
        
        # 提取消息
        message_parts = line.split('|')
        if len(message_parts) > 5:
            log_entry['message'] = message_parts[-1].strip()
        
        return log_entry if 'timestamp' in log_entry else None
    
    def generate_report(self, output_file: str = "log_report.json", hours: int = 24):
        """
        生成综合分析报告
        
        Args:
            output_file: 输出文件路径
            hours: 分析时间范围（小时）
        """
        report = {
            'generated_at': datetime.now().isoformat(),
            'time_range_hours': hours,
            'errors': self.analyze_errors(hours),
            'performance': self.analyze_performance(hours),
            'components': self.analyze_components(hours),
        }
        
        # 保存报告
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, default=str)
        
        return report
    
    def print_summary(self, hours: int = 24):
        """打印分析摘要"""
        errors = self.analyze_errors(hours)
        performance = self.analyze_performance(hours)
        components = self.analyze_components(hours)
        
        print(f"\n{'='*60}")
        print(f"日志分析报告 (最近 {hours} 小时)")
        print(f"{'='*60}")
        
        print(f"\n📊 错误统计:")
        print(f"  - 总错误数: {errors['total_errors']}")
        print(f"  - 主要错误类型: {list(errors['top_error_types'].keys())[:3]}")
        print(f"  - 主要错误组件: {list(errors['top_error_components'].keys())[:3]}")
        
        print(f"\n⚡ 性能统计:")
        print(f"  - 总操作数: {performance['total_operations']}")
        print(f"  - 慢操作数: {performance['slow_operations_count']}")
        if performance['percentiles']:
            print(f"  - P50延迟: {performance['percentiles']['p50']}ms")
            print(f"  - P95延迟: {performance['percentiles']['p95']}ms")
            print(f"  - P99延迟: {performance['percentiles']['p99']}ms")
        
        print(f"\n🔧 组件统计:")
        print(f"  - 活跃组件数: {components['component_count']}")
        if components['most_active']:
            print(f"  - 最活跃组件:")
            for comp, stats in components['most_active'][:3]:
                print(f"    - {comp}: {stats['total_logs']} 条日志")
        
        print(f"\n{'='*60}\n")


# ==============================================================================
# CLI命令
# ==============================================================================

@click.group()
def cli():
    """日志分析工具"""
    pass


@cli.command()
@click.option('--log-dir', default='./logs', help='日志目录路径')
@click.option('--hours', default=24, help='分析时间范围（小时）')
def errors(log_dir, hours):
    """分析错误日志"""
    analyzer = LogAnalyzer(log_dir)
    result = analyzer.analyze_errors(hours)
    print(json.dumps(result, indent=2, default=str))


@cli.command()
@click.option('--log-dir', default='./logs', help='日志目录路径')
@click.option('--hours', default=24, help='分析时间范围（小时）')
def performance(log_dir, hours):
    """分析性能日志"""
    analyzer = LogAnalyzer(log_dir)
    result = analyzer.analyze_performance(hours)
    print(json.dumps(result, indent=2, default=str))


@cli.command()
@click.option('--log-dir', default='./logs', help='日志目录路径')
@click.option('--hours', default=24, help='分析时间范围（小时）')
def components(log_dir, hours):
    """分析组件日志"""
    analyzer = LogAnalyzer(log_dir)
    result = analyzer.analyze_components(hours)
    print(json.dumps(result, indent=2, default=str))


@cli.command()
@click.option('--log-dir', default='./logs', help='日志目录路径')
@click.option('--hours', default=24, help='分析时间范围（小时）')
@click.option('--output', default='log_report.json', help='输出文件路径')
def report(log_dir, hours, output):
    """生成综合分析报告"""
    analyzer = LogAnalyzer(log_dir)
    result = analyzer.generate_report(output, hours)
    print(f"报告已生成: {output}")
    analyzer.print_summary(hours)


@cli.command()
@click.option('--log-dir', default='./logs', help='日志目录路径')
@click.option('--hours', default=24, help='分析时间范围（小时）')
def summary(log_dir, hours):
    """显示分析摘要"""
    analyzer = LogAnalyzer(log_dir)
    analyzer.print_summary(hours)


if __name__ == '__main__':
    cli()