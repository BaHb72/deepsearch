#!/usr/bin/env python
"""
配置文件验证工具
用于检查DeepSearch配置文件的合理性和安全性

使用方法:
    python tools/validate_config.py --env dev
    python tools/validate_config.py --env prod
    python tools/validate_config.py --file deepsearch/config/settings.dev.yaml
"""

import argparse
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

import yaml


class ConfigValidator:
    """配置文件验证器"""

    def __init__(self):
        self.errors: List[str] = []
        self.warnings: List[str] = []
        self.info: List[str] = []

    def validate(self, config_path: str) -> Tuple[bool, Dict[str, List[str]]]:
        """
        验证配置文件

        Args:
            config_path: 配置文件路径

        Returns:
            (是否通过验证, {错误/警告/信息})
        """
        if not os.path.exists(config_path):
            self.errors.append(f"配置文件不存在: {config_path}")
            return False, self._get_results()

        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f)
        except Exception as e:
            self.errors.append(f"配置文件解析失败: {e}")
            return False, self._get_results()

        # 检测环境
        env = config.get("app", {}).get("env", "unknown")
        self.info.append(f"检查环境: {env}")

        # 执行验证
        self._validate_basic(config, env)
        self._validate_security(config, env)
        self._validate_database(config, env)
        self._validate_redis(config, env)
        self._validate_data_sources(config, env)
        self._validate_logging(config, env)
        self._validate_performance(config, env)
        self._validate_monitoring(config, env)

        return len(self.errors) == 0, self._get_results()

    def _get_results(self) -> Dict[str, List[str]]:
        """获取验证结果"""
        return {"errors": self.errors, "warnings": self.warnings, "info": self.info}

    def _validate_basic(self, config: Dict[str, Any], env: str):
        """基础配置验证"""
        app = config.get("app", {})

        # 检查debug模式
        if env == "prod" and app.get("debug", False):
            self.errors.append("生产环境不应开启debug模式")

        # 检查必要字段
        if not app.get("name"):
            self.errors.append("缺少应用名称配置")

    def _validate_security(self, config: Dict[str, Any], env: str):
        """安全配置验证"""
        # 检查敏感信息
        self._check_password_strength(config)
        self._check_api_keys(config)

        # 检查CORS配置
        cors = config.get("webui", {}).get("backend", {}).get("cors", {})
        origins = cors.get("origins", [])
        if env == "prod" and "*" in origins:
            self.warnings.append("生产环境不建议CORS允许所有域名")

    def _validate_database(self, config: Dict[str, Any], env: str):
        """数据库配置验证"""
        db = config.get("database", {}).get("main", {})

        # 检查必要字段
        if not db.get("host"):
            self.errors.append("缺少数据库host配置")
        if not db.get("port"):
            self.errors.append("缺少数据库port配置")
        if not db.get("database"):
            self.errors.append("缺少数据库名称配置")

        # 检查密码
        password = db.get("password", "")
        if password and not self._is_env_var(password):
            if self._is_weak_password(password):
                self.errors.append("数据库密码过于简单")
            if env == "prod":
                self.errors.append("生产环境数据库密码不应明文存储")

        # 检查连接池配置
        if env == "prod" and not db.get("pool"):
            self.warnings.append("生产环境建议配置数据库连接池")

    def _validate_redis(self, config: Dict[str, Any], env: str):
        """Redis配置验证"""
        redis = config.get("database", {}).get("cache", {})

        if not redis.get("enabled"):
            self.warnings.append("Redis缓存未启用")
            return

        # 检查密码
        password = redis.get("password", "")
        if not password and env == "prod":
            self.errors.append("生产环境Redis必须设置密码")
        elif password and not self._is_env_var(password) and env == "prod":
            self.errors.append("生产环境Redis密码不应明文存储")

    def _validate_data_sources(self, config: Dict[str, Any], env: str):
        """数据源配置验证"""
        # 检查新旧配置格式
        has_new = "data_sources" in config
        has_old = "data_providers" in config or "amazingdata" in config

        if has_new and has_old:
            self.warnings.append("存在新旧两种数据源配置格式，建议统一使用data_sources")

        if has_new:
            providers = config.get("data_sources", {}).get("providers", {})

            # 检查AmazingData配置
            amazingdata = providers.get("amazingdata", {})
            if amazingdata.get("enabled"):
                cfg = amazingdata.get("config", {}).get("connection", {})
                username = cfg.get("username", "")
                password = cfg.get("password", "")

                if username and not self._is_env_var(username):
                    self.warnings.append("AmazingData用户名建议使用环境变量")
                if password and not self._is_env_var(password):
                    self.errors.append("AmazingData密码必须使用环境变量")

            # 检查优先级
            priorities = {}
            for name, provider in providers.items():
                priority = provider.get("priority")
                if priority is not None:
                    if priority in priorities:
                        self.errors.append(
                            f"数据源优先级冲突: {name} 和 {priorities[priority]} 都是 {priority}"
                        )
                    priorities[priority] = name

        # 检查旧格式中的重复配置
        if "amazingdata" in config:
            count = 0
            for line in yaml.dump(config).split("\n"):
                if "amazingdata:" in line:
                    count += 1
            if count > 1:
                self.warnings.append("配置文件中存在多处amazingdata配置")

    def _validate_logging(self, config: Dict[str, Any], env: str):
        """日志配置验证"""
        log = config.get("log", {})

        # 检查日志级别
        level = log.get("level", "INFO")
        if env == "prod" and level == "DEBUG":
            self.warnings.append("生产环境不建议使用DEBUG日志级别")

        # 检查日志保留天数
        retention = log.get("retention_days", 7)
        if env == "prod" and retention < 30:
            self.warnings.append(f"生产环境日志保留{retention}天可能太短，建议至少30天")

        # 检查日志格式
        if env == "prod" and not log.get("enable_json"):
            self.info.append("生产环境建议启用JSON格式日志便于分析")

    def _validate_performance(self, config: Dict[str, Any], env: str):
        """性能配置验证"""
        # 检查缓存配置
        cache_config = config.get("performance", {}).get("cache", {})
        if not cache_config:
            self.info.append("未配置性能优化缓存")

        # 检查工作线程数
        workers = config.get("webui", {}).get("backend", {}).get("workers", 1)
        if env == "prod" and workers < 2:
            self.warnings.append("生产环境建议配置多个工作进程")

    def _validate_monitoring(self, config: Dict[str, Any], env: str):
        """监控配置验证"""
        monitoring = config.get("monitoring", {})
        if env == "prod" and not monitoring.get("enabled"):
            self.warnings.append("生产环境建议启用监控")

    def _check_password_strength(self, config: Dict[str, Any]):
        """检查密码强度"""

        # 递归查找所有password字段
        def find_passwords(obj, path=""):
            if isinstance(obj, dict):
                for key, value in obj.items():
                    new_path = f"{path}.{key}" if path else key
                    if "password" in key.lower():
                        if value and not self._is_env_var(value):
                            if self._is_weak_password(value):
                                self.errors.append(f"弱密码: {new_path}")
                    else:
                        find_passwords(value, new_path)
            elif isinstance(obj, list):
                for i, item in enumerate(obj):
                    find_passwords(item, f"{path}[{i}]")

        find_passwords(config)

    def _check_api_keys(self, config: Dict[str, Any]):
        """检查API密钥"""

        # 递归查找所有api_key字段
        def find_api_keys(obj, path=""):
            if isinstance(obj, dict):
                for key, value in obj.items():
                    new_path = f"{path}.{key}" if path else key
                    if "api_key" in key.lower() or "secret" in key.lower():
                        if value and not self._is_env_var(value):
                            self.warnings.append(f"API密钥建议使用环境变量: {new_path}")
                    else:
                        find_api_keys(value, new_path)
            elif isinstance(obj, list):
                for i, item in enumerate(obj):
                    find_api_keys(item, f"{path}[{i}]")

        find_api_keys(config)

    def _is_env_var(self, value: str) -> bool:
        """检查是否是环境变量引用"""
        if not isinstance(value, str):
            return False
        # 检查 ${VAR} 或 ${VAR:default} 格式
        return bool(re.match(r"\$\{[A-Z_][A-Z0-9_]*(?::.*?)?\}", value))

    def _is_weak_password(self, password: str) -> bool:
        """检查密码是否过弱"""
        if not password:
            return True

        # 确保是字符串
        if not isinstance(password, str):
            return False

        # 常见弱密码
        weak_passwords = [
            "123456",
            "password",
            "admin",
            "root",
            "test",
            "111111",
            "123123",
            "000000",
            "666666",
            "888888",
        ]

        if password.lower() in weak_passwords:
            return True

        # 长度检查
        if len(password) < 8:
            return True

        # 纯数字或纯字母
        if password.isdigit() or password.isalpha():
            return True

        return False


def print_results(results: Dict[str, List[str]]):
    """打印验证结果"""
    errors = results.get("errors", [])
    warnings = results.get("warnings", [])
    info = results.get("info", [])

    # 打印信息
    if info:
        print("\n信息:")
        for msg in info:
            print(f"  [INFO] {msg}")

    # 打印警告
    if warnings:
        print("\n警告:")
        for msg in warnings:
            print(f"  [WARN] {msg}")

    # 打印错误
    if errors:
        print("\n错误:")
        for msg in errors:
            print(f"  [ERROR] {msg}")
        print(f"\n发现 {len(errors)} 个错误，必须修复!")
    else:
        print("\n[PASS] 配置验证通过!")

    # 统计
    print(f"\n统计: {len(errors)} 个错误, {len(warnings)} 个警告, {len(info)} 条信息")


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="验证DeepSearch配置文件")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--env", choices=["dev", "prod"], help="验证指定环境的配置")
    group.add_argument("--file", help="验证指定的配置文件")

    args = parser.parse_args()

    # 确定配置文件路径
    if args.env:
        base_dir = Path(__file__).parent.parent
        config_path = base_dir / "deepsearch" / "config" / f"settings.{args.env}.yaml"
    else:
        config_path = Path(args.file)

    # 验证配置
    validator = ConfigValidator()
    passed, results = validator.validate(str(config_path))

    # 打印结果
    print(f"验证配置文件: {config_path}")
    print_results(results)

    # 返回状态码
    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
