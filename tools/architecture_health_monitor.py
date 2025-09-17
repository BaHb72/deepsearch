#!/usr/bin/env python
"""
Architecture Health Monitor for DeepSearch

This tool continuously monitors the health of the system architecture,
tracking metrics, detecting issues, and providing recommendations.
"""

import os
import json
import time
import ast
import subprocess
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass, field, asdict
from collections import defaultdict
import asyncio
import psutil
import schedule


@dataclass
class HealthMetric:
    """Represents a single health metric."""
    name: str
    value: float
    target: float
    unit: str
    status: str  # 'good', 'warning', 'critical'
    timestamp: datetime = field(default_factory=datetime.now)
    
    @property
    def score(self) -> float:
        """Calculate health score (0-100)."""
        if self.target == 0:
            return 100 if self.value == 0 else 0
        
        ratio = self.value / self.target
        if ratio <= 1:
            return min(100, ratio * 100)
        else:
            # Penalize for exceeding target
            return max(0, 100 - (ratio - 1) * 50)
    
    def get_status_emoji(self) -> str:
        """Get emoji for status."""
        return {
            'good': '[GOOD]',
            'warning': '[WARNING]',
            'critical': '[CRITICAL]'
        }.get(self.status, '[UNKNOWN]')


@dataclass
class ArchitectureHealth:
    """Overall architecture health status."""
    timestamp: datetime = field(default_factory=datetime.now)
    metrics: List[HealthMetric] = field(default_factory=list)
    issues: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    overall_score: float = 0.0
    
    def calculate_overall_score(self):
        """Calculate overall health score."""
        if not self.metrics:
            self.overall_score = 0.0
        else:
            self.overall_score = sum(m.score for m in self.metrics) / len(self.metrics)
    
    def get_status(self) -> str:
        """Get overall status."""
        if self.overall_score >= 80:
            return 'healthy'
        elif self.overall_score >= 60:
            return 'warning'
        else:
            return 'critical'


class ArchitectureHealthMonitor:
    """
    Monitors various aspects of architecture health.
    """
    
    def __init__(self, project_root: Path = Path("deepsearch")):
        self.project_root = project_root
        self.history: List[ArchitectureHealth] = []
        self.targets = self._load_targets()
        
    def _load_targets(self) -> Dict[str, Any]:
        """Load target metrics."""
        return {
            'file_count': 200,
            'avg_complexity': 8.0,
            'test_coverage': 90.0,
            'max_file_size': 500,  # lines
            'dependency_depth': 3,
            'circular_deps': 0,
            'code_duplication': 5.0,  # percentage
            'api_response_time': 100,  # ms
            'memory_usage': 500,  # MB
            'error_rate': 0.1,  # percentage
        }
    
    def check_health(self) -> ArchitectureHealth:
        """Perform complete health check."""
        health = ArchitectureHealth()
        
        # Code metrics
        health.metrics.extend(self._check_code_metrics())
        
        # Architecture metrics
        health.metrics.extend(self._check_architecture_metrics())
        
        # Performance metrics
        health.metrics.extend(self._check_performance_metrics())
        
        # Quality metrics
        health.metrics.extend(self._check_quality_metrics())
        
        # Analyze issues
        health.issues = self._analyze_issues(health.metrics)
        
        # Generate recommendations
        health.recommendations = self._generate_recommendations(health.metrics)
        
        # Calculate overall score
        health.calculate_overall_score()
        
        # Store in history
        self.history.append(health)
        
        return health
    
    def _check_code_metrics(self) -> List[HealthMetric]:
        """Check code-related metrics."""
        metrics = []
        
        # File count
        py_files = list(self.project_root.rglob("*.py"))
        py_files = [f for f in py_files if "__pycache__" not in str(f)]
        
        file_count = len(py_files)
        metrics.append(HealthMetric(
            name="file_count",
            value=file_count,
            target=self.targets['file_count'],
            unit="files",
            status='good' if file_count <= self.targets['file_count'] else 'warning'
        ))
        
        # Average complexity
        complexities = []
        for file in py_files[:50]:  # Sample first 50 files for speed
            complexity = self._calculate_complexity(file)
            if complexity:
                complexities.append(complexity)
        
        avg_complexity = sum(complexities) / len(complexities) if complexities else 0
        metrics.append(HealthMetric(
            name="avg_complexity",
            value=avg_complexity,
            target=self.targets['avg_complexity'],
            unit="",
            status='good' if avg_complexity <= self.targets['avg_complexity'] else 
                   'warning' if avg_complexity <= self.targets['avg_complexity'] * 1.5 else 'critical'
        ))
        
        # Max file size
        max_lines = 0
        largest_file = None
        for file in py_files:
            try:
                with open(file, 'r', encoding='utf-8', errors='ignore') as f:
                    lines = len(f.readlines())
                    if lines > max_lines:
                        max_lines = lines
                        largest_file = file
            except:
                pass
        
        metrics.append(HealthMetric(
            name="max_file_size",
            value=max_lines,
            target=self.targets['max_file_size'],
            unit="lines",
            status='good' if max_lines <= self.targets['max_file_size'] else
                   'warning' if max_lines <= self.targets['max_file_size'] * 2 else 'critical'
        ))
        
        return metrics
    
    def _check_architecture_metrics(self) -> List[HealthMetric]:
        """Check architecture-related metrics."""
        metrics = []
        
        # Check for new architecture adoption
        new_dirs = ['domain', 'application', 'infrastructure', 'interfaces']
        adopted = sum(1 for d in new_dirs if (self.project_root / d).exists())
        
        metrics.append(HealthMetric(
            name="hexagonal_adoption",
            value=adopted,
            target=4,
            unit="layers",
            status='good' if adopted == 4 else 'warning' if adopted >= 2 else 'critical'
        ))
        
        # Check dependency direction
        violations = self._check_dependency_violations()
        metrics.append(HealthMetric(
            name="dependency_violations",
            value=violations,
            target=0,
            unit="violations",
            status='good' if violations == 0 else 'warning' if violations <= 5 else 'critical'
        ))
        
        # Module cohesion
        cohesion_score = self._calculate_module_cohesion()
        metrics.append(HealthMetric(
            name="module_cohesion",
            value=cohesion_score,
            target=80,
            unit="%",
            status='good' if cohesion_score >= 80 else 'warning' if cohesion_score >= 60 else 'critical'
        ))
        
        return metrics
    
    def _check_performance_metrics(self) -> List[HealthMetric]:
        """Check performance-related metrics."""
        metrics = []
        
        # Memory usage
        process = psutil.Process()
        memory_mb = process.memory_info().rss / 1024 / 1024
        
        metrics.append(HealthMetric(
            name="memory_usage",
            value=memory_mb,
            target=self.targets['memory_usage'],
            unit="MB",
            status='good' if memory_mb <= self.targets['memory_usage'] else
                   'warning' if memory_mb <= self.targets['memory_usage'] * 1.5 else 'critical'
        ))
        
        # CPU usage
        cpu_percent = psutil.cpu_percent(interval=1)
        metrics.append(HealthMetric(
            name="cpu_usage",
            value=cpu_percent,
            target=50,
            unit="%",
            status='good' if cpu_percent <= 50 else 'warning' if cpu_percent <= 75 else 'critical'
        ))
        
        return metrics
    
    def _check_quality_metrics(self) -> List[HealthMetric]:
        """Check quality-related metrics."""
        metrics = []
        
        # Test coverage (simulated - would run actual coverage tool)
        try:
            result = subprocess.run(
                ["python", "-m", "pytest", "--co", "-q"],
                capture_output=True,
                text=True,
                timeout=10
            )
            test_count = len([l for l in result.stdout.split('\n') if 'test_' in l])
        except:
            test_count = 0
        
        # Estimate coverage based on test count
        estimated_coverage = min(90, test_count * 2)  # Rough estimate
        
        metrics.append(HealthMetric(
            name="test_coverage",
            value=estimated_coverage,
            target=self.targets['test_coverage'],
            unit="%",
            status='good' if estimated_coverage >= self.targets['test_coverage'] else
                   'warning' if estimated_coverage >= 60 else 'critical'
        ))
        
        # Documentation coverage
        doc_coverage = self._calculate_doc_coverage()
        metrics.append(HealthMetric(
            name="doc_coverage",
            value=doc_coverage,
            target=80,
            unit="%",
            status='good' if doc_coverage >= 80 else 'warning' if doc_coverage >= 50 else 'critical'
        ))
        
        return metrics
    
    def _calculate_complexity(self, file_path: Path) -> Optional[int]:
        """Calculate cyclomatic complexity of a file."""
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            tree = ast.parse(content)
            
            complexity = 1
            for node in ast.walk(tree):
                if isinstance(node, (ast.If, ast.For, ast.While, ast.ExceptHandler)):
                    complexity += 1
            return complexity
        except:
            return None
    
    def _check_dependency_violations(self) -> int:
        """Check for dependency rule violations."""
        violations = 0
        
        # Domain should not depend on infrastructure
        domain_path = self.project_root / "domain"
        if domain_path.exists():
            for file in domain_path.rglob("*.py"):
                try:
                    with open(file, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                    if 'from infrastructure' in content or 'import infrastructure' in content:
                        violations += 1
                except:
                    pass
        
        # Application should not depend on interfaces
        app_path = self.project_root / "application"
        if app_path.exists():
            for file in app_path.rglob("*.py"):
                try:
                    with open(file, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                    if 'from interfaces' in content or 'import interfaces' in content:
                        violations += 1
                except:
                    pass
        
        return violations
    
    def _calculate_module_cohesion(self) -> float:
        """Calculate module cohesion score."""
        # Simplified cohesion calculation
        # Real implementation would analyze class/function relationships
        
        total_modules = 0
        cohesive_modules = 0
        
        for module_dir in self.project_root.iterdir():
            if module_dir.is_dir() and not module_dir.name.startswith('_'):
                total_modules += 1
                
                # Check if module has clear responsibility
                py_files = list(module_dir.rglob("*.py"))
                if py_files:
                    # Simple heuristic: modules with similar file names are cohesive
                    file_names = [f.stem for f in py_files]
                    common_prefix = os.path.commonprefix(file_names)
                    if len(common_prefix) > 3:
                        cohesive_modules += 1
        
        return (cohesive_modules / total_modules * 100) if total_modules > 0 else 0
    
    def _calculate_doc_coverage(self) -> float:
        """Calculate documentation coverage."""
        total_functions = 0
        documented_functions = 0
        
        for file in list(self.project_root.rglob("*.py"))[:20]:  # Sample
            try:
                with open(file, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                tree = ast.parse(content)
                
                for node in ast.walk(tree):
                    if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
                        total_functions += 1
                        if ast.get_docstring(node):
                            documented_functions += 1
            except:
                pass
        
        return (documented_functions / total_functions * 100) if total_functions > 0 else 0
    
    def _analyze_issues(self, metrics: List[HealthMetric]) -> List[str]:
        """Analyze metrics to identify issues."""
        issues = []
        
        for metric in metrics:
            if metric.status == 'critical':
                issues.append(f"CRITICAL: {metric.name} is {metric.value:.1f} (target: {metric.target})")
            elif metric.status == 'warning':
                issues.append(f"WARNING: {metric.name} is {metric.value:.1f} (target: {metric.target})")
        
        # Additional analysis
        file_count = next((m for m in metrics if m.name == 'file_count'), None)
        if file_count and file_count.value > file_count.target * 2:
            issues.append("CRITICAL: Codebase is too large, immediate refactoring required")
        
        test_coverage = next((m for m in metrics if m.name == 'test_coverage'), None)
        if test_coverage and test_coverage.value < 50:
            issues.append("CRITICAL: Test coverage dangerously low")
        
        return issues
    
    def _generate_recommendations(self, metrics: List[HealthMetric]) -> List[str]:
        """Generate recommendations based on metrics."""
        recommendations = []
        
        # File count recommendations
        file_count = next((m for m in metrics if m.name == 'file_count'), None)
        if file_count and file_count.value > file_count.target:
            excess = file_count.value - file_count.target
            recommendations.append(f"Delete or consolidate {excess} files to reach target")
        
        # Complexity recommendations
        complexity = next((m for m in metrics if m.name == 'avg_complexity'), None)
        if complexity and complexity.value > complexity.target:
            recommendations.append("Refactor complex functions, extract methods, simplify logic")
        
        # Architecture recommendations
        hexagonal = next((m for m in metrics if m.name == 'hexagonal_adoption'), None)
        if hexagonal and hexagonal.value < hexagonal.target:
            missing = int(hexagonal.target - hexagonal.value)
            recommendations.append(f"Complete hexagonal architecture setup ({missing} layers missing)")
        
        # Test recommendations
        test_coverage = next((m for m in metrics if m.name == 'test_coverage'), None)
        if test_coverage and test_coverage.value < test_coverage.target:
            gap = test_coverage.target - test_coverage.value
            recommendations.append(f"Increase test coverage by {gap:.0f}% - focus on critical paths")
        
        # Performance recommendations
        memory = next((m for m in metrics if m.name == 'memory_usage'), None)
        if memory and memory.value > memory.target:
            recommendations.append("Optimize memory usage: check for leaks, reduce cache sizes")
        
        return recommendations
    
    def generate_report(self, health: ArchitectureHealth) -> str:
        """Generate text report."""
        report = []
        report.append("=" * 60)
        report.append("ARCHITECTURE HEALTH REPORT")
        report.append("=" * 60)
        report.append(f"Timestamp: {health.timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
        report.append(f"Overall Score: {health.overall_score:.1f}/100 ({health.get_status().upper()})")
        report.append("")
        
        # Metrics by category
        categories = {
            'Code': ['file_count', 'avg_complexity', 'max_file_size'],
            'Architecture': ['hexagonal_adoption', 'dependency_violations', 'module_cohesion'],
            'Performance': ['memory_usage', 'cpu_usage'],
            'Quality': ['test_coverage', 'doc_coverage']
        }
        
        for category, metric_names in categories.items():
            report.append(f"\n{category} Metrics:")
            report.append("-" * 40)
            
            for metric in health.metrics:
                if metric.name in metric_names:
                    status_emoji = metric.get_status_emoji()
                    report.append(
                        f"  {status_emoji} {metric.name:20} {metric.value:8.1f} / {metric.target:8.1f} {metric.unit:5} "
                        f"(Score: {metric.score:.0f})"
                    )
        
        # Issues
        if health.issues:
            report.append("\n" + "=" * 60)
            report.append("ISSUES DETECTED")
            report.append("=" * 60)
            for issue in health.issues:
                report.append(f"  - {issue}")
        
        # Recommendations
        if health.recommendations:
            report.append("\n" + "=" * 60)
            report.append("RECOMMENDATIONS")
            report.append("=" * 60)
            for rec in health.recommendations:
                report.append(f"  [+] {rec}")
        
        # Trend analysis
        if len(self.history) > 1:
            report.append("\n" + "=" * 60)
            report.append("TREND ANALYSIS")
            report.append("=" * 60)
            
            prev_health = self.history[-2]
            score_change = health.overall_score - prev_health.overall_score
            
            if score_change > 0:
                report.append(f"  [UP] Score improved by {score_change:.1f} points")
            elif score_change < 0:
                report.append(f"  [DOWN] Score decreased by {abs(score_change):.1f} points")
            else:
                report.append(f"  ➡️ Score unchanged")
            
            # Metric changes
            for metric in health.metrics:
                prev_metric = next((m for m in prev_health.metrics if m.name == metric.name), None)
                if prev_metric:
                    change = metric.value - prev_metric.value
                    if abs(change) > 0.1:
                        direction = "↑" if change > 0 else "↓"
                        report.append(f"    {metric.name}: {direction} {abs(change):.1f}")
        
        return "\n".join(report)
    
    def save_report(self, health: ArchitectureHealth, output_dir: Path = Path("health_reports")):
        """Save health report to file."""
        output_dir.mkdir(exist_ok=True)
        
        # Save JSON
        timestamp = health.timestamp.strftime("%Y%m%d_%H%M%S")
        json_file = output_dir / f"health_{timestamp}.json"
        
        data = {
            'timestamp': health.timestamp.isoformat(),
            'overall_score': health.overall_score,
            'status': health.get_status(),
            'metrics': [
                {
                    'name': m.name,
                    'value': m.value,
                    'target': m.target,
                    'unit': m.unit,
                    'status': m.status,
                    'score': m.score
                }
                for m in health.metrics
            ],
            'issues': health.issues,
            'recommendations': health.recommendations
        }
        
        with open(json_file, 'w') as f:
            json.dump(data, f, indent=2)
        
        # Save text report
        text_file = output_dir / f"health_{timestamp}.txt"
        report = self.generate_report(health)
        with open(text_file, 'w', encoding='utf-8') as f:
            f.write(report)
        
        return json_file, text_file
    
    def create_dashboard_data(self) -> Dict[str, Any]:
        """Create data for dashboard visualization."""
        if not self.history:
            return {}
        
        latest = self.history[-1]
        
        dashboard_data = {
            'current': {
                'score': latest.overall_score,
                'status': latest.get_status(),
                'timestamp': latest.timestamp.isoformat()
            },
            'metrics': {
                m.name: {
                    'value': m.value,
                    'target': m.target,
                    'score': m.score,
                    'status': m.status
                }
                for m in latest.metrics
            },
            'history': [
                {
                    'timestamp': h.timestamp.isoformat(),
                    'score': h.overall_score
                }
                for h in self.history[-24:]  # Last 24 checks
            ],
            'issues_count': len(latest.issues),
            'critical_count': sum(1 for i in latest.issues if 'CRITICAL' in i),
            'warning_count': sum(1 for i in latest.issues if 'WARNING' in i)
        }
        
        return dashboard_data


def continuous_monitoring():
    """Run continuous monitoring."""
    monitor = ArchitectureHealthMonitor()
    
    def check_and_report():
        """Perform health check and generate report."""
        print(f"\n[{datetime.now():%H:%M:%S}] Running health check...")
        
        health = monitor.check_health()
        report = monitor.generate_report(health)
        
        print(report)
        
        # Save reports
        json_file, text_file = monitor.save_report(health)
        print(f"\nReports saved: {json_file}, {text_file}")
        
        # Alert on critical issues
        if health.get_status() == 'critical':
            print("\n[WARNING] CRITICAL HEALTH STATUS - IMMEDIATE ACTION REQUIRED!")
        
        # Create dashboard data
        dashboard_data = monitor.create_dashboard_data()
        with open('dashboard_data.json', 'w') as f:
            json.dump(dashboard_data, f, indent=2)
    
    # Initial check
    check_and_report()
    
    # Schedule periodic checks
    schedule.every(30).minutes.do(check_and_report)
    
    print("\n[INFO] Continuous monitoring started. Press Ctrl+C to stop.")
    print("Checks will run every 30 minutes.")
    
    try:
        while True:
            schedule.run_pending()
            time.sleep(60)
    except KeyboardInterrupt:
        print("\n Monitoring stopped.")


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Architecture Health Monitor')
    parser.add_argument('--check', action='store_true', help='Run single health check')
    parser.add_argument('--monitor', action='store_true', help='Start continuous monitoring')
    parser.add_argument('--history', action='store_true', help='Show health history')
    
    args = parser.parse_args()
    
    monitor = ArchitectureHealthMonitor()
    
    if args.check:
        health = monitor.check_health()
        report = monitor.generate_report(health)
        print(report)
        
        # Save reports
        json_file, text_file = monitor.save_report(health)
        print(f"\nReports saved: {json_file}, {text_file}")
        
    elif args.monitor:
        continuous_monitoring()
        
    elif args.history:
        # Load and display history
        health_reports = Path("health_reports")
        if health_reports.exists():
            reports = sorted(health_reports.glob("health_*.json"))
            print(f"Found {len(reports)} health reports")
            
            for report_file in reports[-10:]:  # Last 10
                with open(report_file) as f:
                    data = json.load(f)
                print(f"{data['timestamp']}: Score={data['overall_score']:.1f}, Status={data['status']}")
    else:
        # Default: run single check
        health = monitor.check_health()
        report = monitor.generate_report(health)
        print(report)


if __name__ == "__main__":
    main()