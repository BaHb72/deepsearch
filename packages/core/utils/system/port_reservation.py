"""
端口预留工具

通过 socket bind 原子性预留端口，解决 TOCTOU（Time-of-check to time-of-use）竞态条件。
用于 Dask Worker 启动时确保多个 Worker 不会抢占同一端口。

Architecture:
    PortReservation 使用 socket.SO_REUSEADDR 选项绑定端口，
    在 Worker 进程启动并绑定端口后释放预留 socket。
    这确保了从检查到使用的原子性。

Usage:
    >>> reservation = PortReservation()
    >>> ports = reservation.reserve_ports(count=2, start_port=58200)
    >>> # 启动 Worker 进程...
    >>> await asyncio.sleep(0.5)  # 等待 Worker 绑定端口
    >>> reservation.release_all()  # 释放预留
"""

from __future__ import annotations

import socket
from typing import List, Optional

from loguru import logger


class PortReservation:
    """端口预留管理器

    使用 socket bind 原子性预留端口，防止 TOCTOU 竞态条件。

    工作原理：
    1. 创建 socket 并设置 SO_REUSEADDR
    2. 绑定到目标端口（原子操作，确保端口被占用）
    3. Worker 进程启动时，由于 SO_REUSEADDR，可以重新绑定同一端口
    4. Worker 绑定成功后，释放预留 socket

    线程安全：
    - 每个 PortReservation 实例独立管理自己的 socket
    - reserve_ports 和 release_all 不是线程安全的，应在单一协程中使用
    """

    def __init__(self) -> None:
        """初始化端口预留管理器"""
        self._reserved_sockets: dict[int, socket.socket] = {}
        self._logger = logger.bind(component="PortReservation")

    def reserve_ports(
        self,
        count: int,
        start_port: int = 58200,
        max_range: int = 100,
        host: str = "0.0.0.0",
    ) -> List[int]:
        """预留指定数量的端口

        通过 socket bind 原子性预留端口，确保返回的端口在调用期间不会被其他进程占用。

        Args:
            count: 需要预留的端口数量
            start_port: 起始端口号
            max_range: 搜索范围（从 start_port 到 start_port + max_range）
            host: 绑定的主机地址（默认 0.0.0.0 表示所有接口）

        Returns:
            预留成功的端口列表

        Raises:
            RuntimeError: 无法在指定范围内找到足够的可用端口

        Example:
            >>> reservation = PortReservation()
            >>> ports = reservation.reserve_ports(count=2)
            >>> print(ports)  # [58200, 58201]
        """
        reserved_ports: List[int] = []

        for port in range(start_port, start_port + max_range):
            if len(reserved_ports) >= count:
                break

            sock = self._try_reserve_port(port, host)
            if sock is not None:
                self._reserved_sockets[port] = sock
                reserved_ports.append(port)
                self._logger.debug(f"端口 {port} 已预留")
            else:
                self._logger.debug(f"端口 {port} 预留失败（已被占用）")

        if len(reserved_ports) < count:
            # 释放已预留的端口
            self.release_all()
            raise RuntimeError(
                f"无法在范围 {start_port}-{start_port + max_range} 内预留 {count} 个端口。"
                f"仅找到 {len(reserved_ports)} 个可用端口。"
            )

        self._logger.info(f"成功预留 {count} 个端口: {reserved_ports}")
        return reserved_ports

    def _try_reserve_port(self, port: int, host: str) -> Optional[socket.socket]:
        """尝试预留单个端口

        Args:
            port: 要预留的端口
            host: 绑定的主机地址

        Returns:
            成功时返回绑定的 socket，失败时返回 None
        """
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            # 设置 SO_REUSEADDR 允许端口重用
            # 这样 Worker 进程可以在我们持有 socket 时绑定同一端口
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

            # 尝试绑定端口（原子操作）
            sock.bind((host, port))

            # 不调用 listen()，只是占住端口
            return sock

        except OSError:
            # 端口已被占用
            sock.close()
            return None
        except Exception as e:
            self._logger.warning(f"预留端口 {port} 时发生异常: {e}")
            sock.close()
            return None

    def release_port(self, port: int) -> bool:
        """释放单个预留的端口

        Args:
            port: 要释放的端口

        Returns:
            True 如果成功释放，False 如果端口未被预留
        """
        sock = self._reserved_sockets.pop(port, None)
        if sock is not None:
            try:
                sock.close()
                self._logger.debug(f"端口 {port} 预留已释放")
                return True
            except Exception as e:
                self._logger.warning(f"释放端口 {port} 时发生异常: {e}")
                return False
        return False

    def release_all(self) -> None:
        """释放所有预留的端口"""
        ports = list(self._reserved_sockets.keys())
        for port in ports:
            self.release_port(port)

        if ports:
            self._logger.info(f"已释放 {len(ports)} 个预留端口")

    @property
    def reserved_ports(self) -> List[int]:
        """获取当前预留的端口列表"""
        return list(self._reserved_sockets.keys())

    def __enter__(self) -> "PortReservation":
        """支持 with 语句"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """退出 with 语句时自动释放所有端口"""
        self.release_all()

    def __del__(self) -> None:
        """析构时确保释放所有端口"""
        try:
            self.release_all()
        except Exception:
            pass


__all__ = ["PortReservation"]
