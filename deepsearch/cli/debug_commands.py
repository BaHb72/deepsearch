"""
调试命令行工具

提供错误分析、性能监控、内存管理等调试功能
"""
import click
import json
import time
import psutil
from datetime import datetime
from pathlib import Path
from typing import Optional

from loguru import logger
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.live import Live
from rich.layout import Layout

# 延迟导入以避免循环依赖
def get_error_handler():
    from deepsearch.core.utils.error_handler import error_handler
    return error_handler

def get_profiler():
    from deepsearch.debug.performance_profiler import profiler
    return profiler

def get_memory_manager():
    from deepsearch.memory.smart_memory import memory_manager
    return memory_manager

def get_query_optimizer():
    from deepsearch.database.query_optimizer import query_optimizer
    return query_optimizer


console = Console()


@click.group()
def debug():
    """调试工具命令组"""
    pass


@debug.command()
@click.option('--last', default=10, help='显示最近N条错误')
@click.option('--export', is_flag=True, help='导出到文件')
def errors(last, export):
    """查看错误历史"""
    error_history = get_error_handler().get_error_history(last)
    
    if not error_history:
        console.print("[yellow]没有错误记录[/yellow]")
        return
        
    # 创建表格
    table = Table(title=f"最近 {last} 条错误", show_header=True, header_style="bold magenta")
    table.add_column("时间", style="cyan", no_wrap=True)
    table.add_column("类型", style="red")
    table.add_column("错误信息", style="yellow")
    table.add_column("严重程度", style="magenta")
    
    for error in error_history:
        timestamp = error.get('timestamp', 'N/A')
        error_type = error.get('type', 'Unknown')
        message = error.get('error', 'No message')[:50] + '...'
        severity = error.get('diagnosis', {}).get('severity', 'UNKNOWN')
        
        # 根据严重程度设置颜色
        severity_color = {
            'CRITICAL': 'red',
            'HIGH': 'orange',
            'MEDIUM': 'yellow',
            'LOW': 'green'
        }.get(severity, 'white')
        
        table.add_row(
            timestamp,
            error_type,
            message,
            f"[{severity_color}]{severity}[/{severity_color}]"
        )
        
    console.print(table)
    
    # 显示解决方案
    if error_history:
        latest_error = error_history[-1]
        if solutions := latest_error.get('solutions'):
            console.print("\n[bold cyan]最新错误的解决方案:[/bold cyan]")
            for i, solution in enumerate(solutions, 1):
                console.print(f"\n[green]方案 {i}: {solution.get('title', '未命名')}[/green]")
                for step in solution.get('steps', []):
                    console.print(f"  • {step}")
                    
    # 导出到文件
    if export:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filepath = f"logs/errors/error_report_{timestamp}.json"
        Path(filepath).parent.mkdir(parents=True, exist_ok=True)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(error_history, f, ensure_ascii=False, indent=2, default=str)
            
        console.print(f"\n[green]错误报告已导出到: {filepath}[/green]")


@debug.command()
@click.option('--module', '-m', help='要分析的模块')
@click.option('--threshold', default=100, help='慢操作阈值(ms)')
@click.option('--export', is_flag=True, help='导出报告')
def profile(module, threshold, export):
    """性能分析"""
    if threshold:
        get_profiler().set_threshold(threshold)
        
    if module:
        console.print(f"[cyan]开始分析模块: {module}[/cyan]")
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            task = progress.add_task("分析中...", total=None)
            
            # 导入并运行模块
            try:
                with get_profiler().profile(f"module.{module}"):
                    __import__(f'deepsearch.{module}')
                    time.sleep(1)  # 给一些时间让模块运行
            except ImportError as e:
                console.print(f"[red]模块导入失败: {e}[/red]")
                return
                
    # 获取性能报告
    report = get_profiler().get_report()
    
    # 显示性能统计
    if operations := report.get('operations'):
        table = Table(title="性能统计", show_header=True, header_style="bold cyan")
        table.add_column("操作", style="cyan")
        table.add_column("调用次数", justify="right")
        table.add_column("平均耗时(ms)", justify="right")
        table.add_column("最大耗时(ms)", justify="right")
        table.add_column("P95(ms)", justify="right")
        
        for op_name, stats in operations.items():
            if stats['count'] > 0:
                table.add_row(
                    op_name[:40],
                    str(stats['count']),
                    f"{stats['duration']['avg_ms']:.2f}",
                    f"{stats['duration']['max_ms']:.2f}",
                    f"{stats['duration']['p95_ms']:.2f}"
                )
                
        console.print(table)
        
    # 显示慢操作
    if slow_ops := report.get('slow_operations'):
        console.print("\n[bold red]慢操作检测:[/bold red]")
        for op in slow_ops[-5:]:  # 显示最近5个
            console.print(f"  • {op['operation']}: {op['duration_ms']:.2f}ms @ {op['timestamp']}")
            
    # 显示优化建议
    suggestions = get_profiler().auto_optimize_suggestions()
    if suggestions:
        console.print("\n[bold yellow]优化建议:[/bold yellow]")
        for s in suggestions[:5]:  # 显示前5个建议
            priority_color = {
                'HIGH': 'red',
                'MEDIUM': 'yellow', 
                'LOW': 'green'
            }.get(s.get('priority', 'LOW'), 'white')
            
            console.print(f"\n[{priority_color}]优先级: {s.get('priority', 'UNKNOWN')}[/{priority_color}]")
            console.print(f"  操作: {s['operation']}")
            console.print(f"  问题: {s['issue']}")
            console.print(f"  当前: {s['current']}")
            console.print(f"  建议: {s['suggestion']}")
            
    # 导出报告
    if export:
        filepath = get_profiler().export_report()
        console.print(f"\n[green]性能报告已导出到: {filepath}[/green]")


@debug.command()
@click.option('--top', default=10, help='显示前N个大对象')
@click.option('--cleanup', is_flag=True, help='执行内存清理')
@click.option('--analyze', is_flag=True, help='分析内存使用')
def memory(top, cleanup, analyze):
    """内存分析"""
    # 获取内存信息
    memory_info = get_memory_manager().get_memory_info()
    
    # 显示系统内存
    system_mem = memory_info['system']
    process_mem = memory_info['process']
    
    panel = Panel(
        f"[cyan]系统内存:[/cyan] {system_mem['percent']:.1f}% "
        f"({system_mem['used'] / 1024 / 1024 / 1024:.2f}GB / "
        f"{system_mem['total'] / 1024 / 1024 / 1024:.2f}GB)\n"
        f"[cyan]进程内存:[/cyan] {process_mem['rss'] / 1024 / 1024:.2f}MB "
        f"({process_mem['percent']:.1f}%)\n"
        f"[cyan]线程数:[/cyan] {process_mem['num_threads']}",
        title="内存状态",
        border_style="green"
    )
    console.print(panel)
    
    # 显示大对象
    large_objects = get_memory_manager().get_large_objects(top)
    if large_objects:
        table = Table(title=f"Top {top} 大对象", show_header=True)
        table.add_column("名称", style="cyan")
        table.add_column("大小(MB)", justify="right")
        table.add_column("类型", style="yellow")
        
        for obj in large_objects:
            table.add_row(
                obj['name'][:30],
                f"{obj['size_mb']:.2f}",
                obj['type']
            )
            
        console.print(table)
        
    # 内存分析
    if analyze:
        console.print("\n[cyan]分析内存使用...[/cyan]")
        analysis = get_memory_manager().analyze_memory_usage()
        
        # 显示趋势
        if trends := analysis.get('trends'):
            if trends.get('growing'):
                console.print(f"[yellow]⚠ 内存使用呈增长趋势[/yellow]")
                if time_to_limit := trends.get('time_to_limit_minutes'):
                    console.print(f"[red]预计 {time_to_limit:.1f} 分钟后达到内存限制[/red]")
                    
        # 显示建议
        if recommendations := analysis.get('recommendations'):
            console.print("\n[bold yellow]内存优化建议:[/bold yellow]")
            for rec in recommendations:
                level_color = {
                    'WARNING': 'yellow',
                    'ERROR': 'red',
                    'INFO': 'cyan'
                }.get(rec['level'], 'white')
                
                console.print(f"[{level_color}]• {rec['message']}[/{level_color}]")
                console.print(f"  {rec['action']}")
                
    # 执行清理
    if cleanup:
        console.print("\n[cyan]执行内存清理...[/cyan]")
        
        with console.status("[bold green]清理中...") as status:
            cleanup_stats = get_memory_manager().cleanup(force=False)
            
        console.print(f"[green]✓ 清理完成:[/green]")
        console.print(f"  • GC回收对象: {cleanup_stats['gc_collected']}")
        console.print(f"  • 清理大对象: {cleanup_stats['objects_cleared']}")
        console.print(f"  • 清理缓存: {cleanup_stats['cache_cleared']}")
        console.print(f"  • 释放内存: {cleanup_stats['memory_freed'] / 1024 / 1024:.2f}MB")


@debug.command()
@click.option('--top', default=10, help='显示前N个慢查询')
@click.option('--analyze', is_flag=True, help='分析N+1问题')
@click.option('--suggest', is_flag=True, help='生成索引建议')
def slow_queries(top, analyze, suggest):
    """慢查询分析"""
    # 获取慢查询
    slow_queries_list = get_query_optimizer().get_slow_queries(top)
    
    if not slow_queries_list:
        console.print("[yellow]没有慢查询记录[/yellow]")
        return
        
    # 显示慢查询
    table = Table(title=f"Top {top} 慢查询", show_header=True)
    table.add_column("查询", style="cyan", width=50)
    table.add_column("执行次数", justify="right")
    table.add_column("平均耗时(s)", justify="right")
    table.add_column("最大耗时(s)", justify="right")
    
    for sq in slow_queries_list:
        table.add_row(
            sq['query'][:50] + '...' if len(sq['query']) > 50 else sq['query'],
            str(sq['executions']),
            f"{sq['avg_time']:.2f}",
            f"{sq['max_time']:.2f}"
        )
        
    console.print(table)
    
    # N+1问题检测
    if analyze:
        console.print("\n[cyan]检测N+1查询问题...[/cyan]")
        
        # 这里需要session对象，简化处理
        n_plus_one = get_query_optimizer().n_plus_one_detections
        
        if n_plus_one:
            console.print("[red]检测到N+1查询问题:[/red]")
            for detection in n_plus_one:
                console.print(f"  • 模式: {detection['pattern'][:50]}...")
                console.print(f"    重复次数: {detection['count']}")
                console.print(f"    建议: {detection['suggestion']}")
        else:
            console.print("[green]未检测到N+1查询问题[/green]")
            
    # 索引建议
    if suggest:
        console.print("\n[cyan]生成索引建议...[/cyan]")
        
        # 这里需要engine对象，简化处理
        suggestions = get_query_optimizer().index_suggestions
        
        if suggestions:
            console.print("[yellow]索引优化建议:[/yellow]")
            for sug in suggestions[:5]:
                if sug.get('type') == 'composite':
                    console.print(f"  • 复合索引: {sug['index_name']}")
                    console.print(f"    字段: {', '.join(sug['columns'])}")
                else:
                    console.print(f"  • 索引: {sug['index_name']}")
                    console.print(f"    表: {sug['table']}, 字段: {sug['column']}")
                console.print(f"    原因: {sug['reason']}")
        else:
            console.print("[green]暂无索引建议[/green]")


@debug.command()
def monitor():
    """实时监控"""
    layout = Layout()
    layout.split_column(
        Layout(name="header", size=3),
        Layout(name="body"),
        Layout(name="footer", size=3)
    )
    
    layout["header"].update(Panel("[bold cyan]DeepSearch 实时监控[/bold cyan]", border_style="cyan"))
    layout["footer"].update(Panel("按 Ctrl+C 退出", border_style="green"))
    
    # 分割主体区域
    layout["body"].split_row(
        Layout(name="left"),
        Layout(name="right")
    )
    
    def get_monitor_data():
        """获取监控数据"""
        # 系统信息
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        process = psutil.Process()
        
        # 性能统计
        perf_report = get_profiler().get_report()
        total_ops = perf_report.get('summary', {}).get('total_operations', 0)
        slow_ops = len(perf_report.get('slow_operations', []))
        
        # 内存信息
        memory_info = get_memory_manager().get_memory_info()
        large_objects = len(get_memory_manager().large_objects)
        
        # 查询统计
        query_report = get_query_optimizer().get_optimization_report()
        total_queries = query_report.get('total_queries', 0)
        slow_queries_count = len(query_report.get('slow_queries', []))
        
        return {
            'cpu': cpu_percent,
            'memory': memory.percent,
            'process_memory': process.memory_info().rss / 1024 / 1024,
            'threads': process.num_threads(),
            'total_ops': total_ops,
            'slow_ops': slow_ops,
            'large_objects': large_objects,
            'total_queries': total_queries,
            'slow_queries': slow_queries_count
        }
        
    with Live(layout, refresh_per_second=1, console=console) as live:
        while True:
            try:
                data = get_monitor_data()
                
                # 更新左侧面板
                left_content = f"""[cyan]系统资源[/cyan]
CPU使用率: {data['cpu']:.1f}%
内存使用率: {data['memory']:.1f}%
进程内存: {data['process_memory']:.2f}MB
线程数: {data['threads']}

[cyan]性能统计[/cyan]
总操作数: {data['total_ops']}
慢操作数: {data['slow_ops']}
"""
                layout["left"].update(Panel(left_content, title="系统状态", border_style="green"))
                
                # 更新右侧面板
                right_content = f"""[cyan]内存管理[/cyan]
大对象数: {data['large_objects']}

[cyan]数据库[/cyan]
总查询数: {data['total_queries']}
慢查询数: {data['slow_queries']}

[cyan]时间[/cyan]
{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
                layout["right"].update(Panel(right_content, title="应用状态", border_style="blue"))
                
                time.sleep(1)
                
            except KeyboardInterrupt:
                break
                
    console.print("\n[green]监控已停止[/green]")


@debug.command()
def reset():
    """重置所有调试数据"""
    if click.confirm("确定要重置所有调试数据吗？"):
        # 重置错误处理器
        get_error_handler().clear_error_history()
        
        # 重置性能分析器
        get_profiler().reset()
        
        # 重置内存管理器
        get_memory_manager().reset()
        
        # 重置查询优化器
        get_query_optimizer().clear_stats()
        
        console.print("[green]✓ 所有调试数据已重置[/green]")
    else:
        console.print("[yellow]操作已取消[/yellow]")


@debug.command()
@click.option('--format', type=click.Choice(['json', 'html', 'text']), default='json', help='报告格式')
def report(format):
    """生成完整调试报告"""
    console.print("[cyan]生成调试报告...[/cyan]")
    
    report_data = {
        'timestamp': datetime.now().isoformat(),
        'errors': {
            'recent': get_error_handler().get_error_history(10),
            'count': len(get_error_handler().error_history)
        },
        'performance': get_profiler().get_report(),
        'memory': get_memory_manager().get_memory_info(),
        'database': get_query_optimizer().get_optimization_report()
    }
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    if format == 'json':
        filepath = f"logs/debug/report_{timestamp}.json"
        Path(filepath).parent.mkdir(parents=True, exist_ok=True)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(report_data, f, ensure_ascii=False, indent=2, default=str)
            
    elif format == 'html':
        filepath = f"logs/debug/report_{timestamp}.html"
        Path(filepath).parent.mkdir(parents=True, exist_ok=True)
        
        # 生成HTML报告
        html_content = generate_html_report(report_data)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(html_content)
            
    else:  # text
        filepath = f"logs/debug/report_{timestamp}.txt"
        Path(filepath).parent.mkdir(parents=True, exist_ok=True)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(f"DeepSearch 调试报告\n")
            f.write(f"生成时间: {report_data['timestamp']}\n")
            f.write("=" * 80 + "\n\n")
            
            # 写入各部分内容
            f.write("错误统计:\n")
            f.write(f"  总错误数: {report_data['errors']['count']}\n\n")
            
            f.write("性能统计:\n")
            if summary := report_data['performance'].get('summary'):
                f.write(f"  总操作数: {summary.get('total_operations', 0)}\n")
                f.write(f"  总耗时: {summary.get('total_time_ms', 0):.2f}ms\n\n")
                
    console.print(f"[green]报告已生成: {filepath}[/green]")


def generate_html_report(data):
    """生成HTML报告"""
    return f"""
<!DOCTYPE html>
<html>
<head>
    <title>DeepSearch 调试报告</title>
    <meta charset="utf-8">
    <style>
        body {{ font-family: Arial, sans-serif; padding: 20px; background: #f5f5f5; }}
        h1 {{ color: #333; }}
        .section {{ background: white; padding: 20px; margin: 20px 0; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        .metric {{ display: inline-block; margin: 10px 20px; }}
        .metric-value {{ font-size: 24px; font-weight: bold; color: #2196F3; }}
        .metric-label {{ color: #666; font-size: 14px; }}
        table {{ width: 100%; border-collapse: collapse; }}
        th, td {{ padding: 10px; text-align: left; border-bottom: 1px solid #ddd; }}
        th {{ background: #f0f0f0; }}
    </style>
</head>
<body>
    <h1>DeepSearch 调试报告</h1>
    <p>生成时间: {data['timestamp']}</p>
    
    <div class="section">
        <h2>错误统计</h2>
        <div class="metric">
            <div class="metric-value">{data['errors']['count']}</div>
            <div class="metric-label">总错误数</div>
        </div>
    </div>
    
    <div class="section">
        <h2>性能概览</h2>
        <pre>{json.dumps(data['performance'].get('summary', {}), indent=2)}</pre>
    </div>
    
    <div class="section">
        <h2>内存使用</h2>
        <pre>{json.dumps(data['memory'], indent=2)}</pre>
    </div>
    
    <div class="section">
        <h2>数据库性能</h2>
        <pre>{json.dumps(data['database'].get('statistics', {}), indent=2)}</pre>
    </div>
</body>
</html>
"""


if __name__ == '__main__':
    debug()