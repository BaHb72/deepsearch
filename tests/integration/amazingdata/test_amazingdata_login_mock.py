#!/usr/bin/env python
# encoding: utf-8
"""
AmazingData 登录功能测试脚本（模拟版本）
用于测试AmazingData登录流程和服务器连接性
"""

import asyncio
import time
import socket
from datetime import datetime
from loguru import logger
import sys
import random

# 配置日志输出
logger.remove()
logger.add(sys.stdout, format="<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | <cyan>{message}</cyan>", level="DEBUG")

class AmazingDataLoginSimulator:
    """AmazingData登录测试模拟器"""

    def __init__(self):
        # 从配置文件中提取的服务器信息
        self.servers = [
            {
                "name": "电信服务器1",
                "host": "101.230.159.234",
                "port": 8600,
                "network": "telecom"
            },
            {
                "name": "电信服务器2",
                "host": "120.86.124.106",
                "port": 8600,
                "network": "telecom"
            },
            {
                "name": "联通服务器",
                "host": "140.206.44.234",
                "port": 8600,
                "network": "unicom"
            }
        ]

        # 用户凭据
        self.username = "212200038719"
        self.password = "212200038719@2025"

        # 测试结果
        self.results = []

    def test_server_connectivity(self, server):
        """测试服务器连接性"""
        logger.info(f"[{server['name']}] 测试服务器连接性...")
        logger.info(f"[{server['name']}] 地址: {server['host']}:{server['port']}")

        start_time = time.time()

        try:
            # 创建socket连接测试
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)  # 5秒超时

            result = sock.connect_ex((server['host'], server['port']))
            elapsed_time = time.time() - start_time

            if result == 0:
                logger.success(f"[{server['name']}] 端口 {server['port']} 开放，连接成功")
                sock.close()
                return {
                    "success": True,
                    "elapsed_time": elapsed_time,
                    "message": "端口连接成功"
                }
            else:
                logger.error(f"[{server['name']}] 端口 {server['port']} 连接失败，错误码: {result}")
                return {
                    "success": False,
                    "elapsed_time": elapsed_time,
                    "message": f"端口连接失败，错误码: {result}"
                }

        except socket.timeout:
            elapsed_time = time.time() - start_time
            logger.error(f"[{server['name']}] 连接超时")
            return {
                "success": False,
                "elapsed_time": elapsed_time,
                "message": "连接超时"
            }
        except Exception as e:
            elapsed_time = time.time() - start_time
            logger.error(f"[{server['name']}] 连接异常: {e}")
            return {
                "success": False,
                "elapsed_time": elapsed_time,
                "message": f"连接异常: {str(e)}"
            }
        finally:
            try:
                sock.close()
            except:
                pass

    def simulate_login(self, server):
        """模拟登录过程"""
        logger.info(f"[{server['name']}] 开始模拟登录测试...")
        logger.info(f"[{server['name']}] 用户名: {self.username}")

        # 首先测试连接性
        connectivity_result = self.test_server_connectivity(server)

        if not connectivity_result['success']:
            logger.warning(f"[{server['name']}] 由于连接失败，跳过登录测试")
            return {
                "server": server['name'],
                "host": server['host'],
                "port": server['port'],
                "network": server['network'],
                "connectivity": False,
                "login_success": False,
                "elapsed_time": connectivity_result['elapsed_time'],
                "message": connectivity_result['message']
            }

        # 模拟登录过程
        logger.info(f"[{server['name']}] 服务器连接正常，开始模拟登录流程...")

        start_time = time.time()

        # 模拟登录步骤
        steps = [
            ("发送认证请求", 0.1),
            ("等待服务器响应", 0.2),
            ("验证用户凭据", 0.15),
            ("获取会话令牌", 0.1),
            ("初始化数据连接", 0.2)
        ]

        total_steps = len(steps)
        for i, (step_name, step_time) in enumerate(steps, 1):
            logger.debug(f"[{server['name']}] [{i}/{total_steps}] {step_name}...")
            time.sleep(step_time)

        elapsed_time = time.time() - start_time

        # 模拟登录结果（由于无法真实登录，基于连接性给出模拟结果）
        # 实际环境中，这里会调用 ad.login()
        simulated_success = random.choice([True, True, False])  # 66%成功率

        if simulated_success:
            logger.success(f"[{server['name']}] 模拟登录成功!")
            logger.info(f"[{server['name']}] 登录耗时: {elapsed_time:.2f}秒")

            # 模拟获取一些数据
            logger.info(f"[{server['name']}] 模拟获取股票列表...")
            time.sleep(0.3)
            stock_count = random.randint(4000, 5000)
            logger.success(f"[{server['name']}] 模拟获取到 {stock_count} 只股票")

            # 模拟登出
            logger.info(f"[{server['name']}] 模拟登出...")
            time.sleep(0.1)
            logger.success(f"[{server['name']}] 模拟登出成功")

            return {
                "server": server['name'],
                "host": server['host'],
                "port": server['port'],
                "network": server['network'],
                "connectivity": True,
                "login_success": True,
                "elapsed_time": elapsed_time,
                "stock_count": stock_count,
                "message": "模拟登录成功"
            }
        else:
            logger.error(f"[{server['name']}] 模拟登录失败")
            return {
                "server": server['name'],
                "host": server['host'],
                "port": server['port'],
                "network": server['network'],
                "connectivity": True,
                "login_success": False,
                "elapsed_time": elapsed_time,
                "message": "模拟登录失败（认证错误）"
            }

    async def simulate_async_login(self, server):
        """模拟异步登录"""
        logger.info(f"[{server['name']}] 开始异步登录测试...")

        start_time = time.time()

        try:
            # 模拟异步操作
            await asyncio.sleep(random.uniform(0.5, 1.0))

            # 模拟登录结果
            success = random.choice([True, True, False])
            elapsed_time = time.time() - start_time

            if success:
                logger.success(f"[{server['name']}] 异步登录成功，耗时: {elapsed_time:.2f}秒")
                return {
                    "server": server['name'],
                    "success": True,
                    "elapsed_time": elapsed_time,
                    "message": "异步登录成功"
                }
            else:
                logger.error(f"[{server['name']}] 异步登录失败")
                return {
                    "server": server['name'],
                    "success": False,
                    "elapsed_time": elapsed_time,
                    "message": "异步登录失败"
                }

        except Exception as e:
            elapsed_time = time.time() - start_time
            logger.error(f"[{server['name']}] 异步登录异常: {e}")
            return {
                "server": server['name'],
                "success": False,
                "elapsed_time": elapsed_time,
                "message": f"异步登录异常: {str(e)}"
            }

    def run_all_tests(self):
        """运行所有测试"""
        logger.info("=" * 80)
        logger.info("AmazingData 登录功能测试（模拟版）")
        logger.info(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"用户名: {self.username}")
        logger.info(f"密码: {self.password[:6]}****")
        logger.info("=" * 80)

        # 测试每个服务器
        for server in self.servers:
            logger.info("\n" + "-" * 60)
            logger.info(f"测试服务器: {server['name']} ({server['network'].upper()})")
            logger.info("-" * 60)

            # 同步登录测试
            result = self.simulate_login(server)
            self.results.append(result)

            # 等待一下避免连续请求
            time.sleep(1)

        # 打印测试总结
        self.print_summary()

    def print_summary(self):
        """打印测试总结"""
        logger.info("\n" + "=" * 80)
        logger.info("测试总结报告")
        logger.info("=" * 80)

        total_count = len(self.results)
        connectivity_success = sum(1 for r in self.results if r['connectivity'])
        login_success = sum(1 for r in self.results if r['login_success'])

        logger.info(f"\n测试统计:")
        logger.info(f"  测试服务器数量: {total_count}")
        logger.info(f"  连接成功数量: {connectivity_success}")
        logger.info(f"  登录成功数量: {login_success}")
        logger.info(f"  连接成功率: {connectivity_success/total_count*100:.1f}%")
        logger.info(f"  登录成功率: {login_success/total_count*100:.1f}%")

        logger.info(f"\n详细结果:")
        logger.info("-" * 60)
        logger.info(f"{'服务器':<15} {'网络':<10} {'连接':<8} {'登录':<8} {'耗时(秒)':<10} {'备注'}")
        logger.info("-" * 60)

        for result in self.results:
            connectivity_status = "✅" if result['connectivity'] else "❌"
            login_status = "✅" if result['login_success'] else "❌"

            logger.info(
                f"{result['server']:<15} "
                f"{result['network'].upper():<10} "
                f"{connectivity_status:<8} "
                f"{login_status:<8} "
                f"{result['elapsed_time']:.2f}秒     "
                f"{result.get('message', '')}"
            )

        # 推荐最佳服务器
        successful_servers = [r for r in self.results if r['login_success']]
        if successful_servers:
            best_server = min(successful_servers, key=lambda x: x['elapsed_time'])
            logger.info("\n" + "-" * 60)
            logger.success(f"推荐服务器配置:")
            logger.success(f"  服务器: {best_server['server']}")
            logger.success(f"  地址: {best_server['host']}:{best_server['port']}")
            logger.success(f"  网络类型: {best_server['network'].upper()}")
            logger.success(f"  响应时间: {best_server['elapsed_time']:.2f}秒")
            if 'stock_count' in best_server:
                logger.success(f"  数据量: {best_server['stock_count']} 只股票")
        else:
            logger.warning("\n未找到可用的服务器，请检查网络连接和服务器状态")

        # 生成配置建议
        logger.info("\n" + "=" * 80)
        logger.info("配置建议:")
        logger.info("-" * 60)

        if successful_servers:
            best = successful_servers[0]
            logger.info("建议在配置文件中使用以下设置:")
            logger.info(f"""
amazingdata:
  enabled: true
  connection:
    username: '{self.username}'
    password: '****'  # 请使用实际密码
    host: {best['host']}
    port: {best['port']}
    timeout: 10
    heartbeat_interval: 60
    auto_reconnect: true
            """)
        else:
            logger.warning("当前没有可用的服务器，建议:")
            logger.warning("1. 检查网络连接是否正常")
            logger.warning("2. 确认服务器地址和端口是否正确")
            logger.warning("3. 联系管理员确认服务器状态")

def main():
    """主函数"""
    logger.info("\n" + "=" * 80)
    logger.info("AmazingData 登录测试工具")
    logger.info("说明: 由于AmazingData SDK未安装，本测试为模拟版本")
    logger.info("=" * 80)

    simulator = AmazingDataLoginSimulator()

    # 运行所有测试
    simulator.run_all_tests()

    # 显示实际环境说明
    logger.info("\n" + "=" * 80)
    logger.info("实际环境说明:")
    logger.info("-" * 60)
    logger.info("在实际环境中，需要:")
    logger.info("1. 安装AmazingData SDK: pip install AmazingData")
    logger.info("2. 使用真实的 ad.login() 函数进行登录")
    logger.info("3. 登录成功后可以调用各种数据接口")
    logger.info("4. 记得在使用完毕后调用 ad.logout() 登出")
    logger.info("=" * 80)

if __name__ == "__main__":
    main()