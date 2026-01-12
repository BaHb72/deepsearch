"""Distributed session management for AmazingData SDK using Redis.

This module provides cross-process login state coordination to ensure:
1. Only one worker performs SDK login at any given time
2. All workers share the login session state
3. Automatic failover if the leader crashes

Usage:
    manager = DistributedSessionManager(redis_url="redis://localhost:6379")
    await manager.ensure_login(login_callback=my_login_func)
"""

from __future__ import annotations

import asyncio
import json
import os
import uuid
from datetime import datetime
from typing import Any, Awaitable, Callable, Optional

from loguru import logger

# Type aliases for login callbacks
LoginCallback = Callable[[], Awaitable[bool]]
LogoutCallback = Callable[[], Awaitable[None]]


class DistributedSessionManager:
    """Redis-based distributed session manager for AmazingData SDK.

    Ensures only one worker in the cluster performs login, while all others
    reuse the shared session state.

    Key features:
    - Distributed lock with TTL (auto-release on crash)
    - Shared session state via Redis
    - Heartbeat mechanism for leader health
    - Graceful fallback to local-only mode if Redis unavailable
    """

    LOCK_KEY = "amazingdata:login:lock"
    SESSION_KEY = "amazingdata:session"
    LOCK_TTL = 30  # seconds
    HEARTBEAT_INTERVAL = 10  # seconds
    SESSION_TTL = 60  # seconds (2x heartbeat for safety margin)

    def __init__(
        self,
        redis_url: str = "redis://localhost:6379",
        worker_id: Optional[str] = None,
    ) -> None:
        """Initialize the distributed session manager.

        Args:
            redis_url: Redis connection URL.
            worker_id: Unique identifier for this worker. Auto-generated if not provided.
        """
        self._redis_url = redis_url
        self._worker_id = worker_id or f"worker-{uuid.uuid4().hex[:8]}-{os.getpid()}"
        self._redis: Any = None
        self._is_leader = False
        self._heartbeat_task: Optional[asyncio.Task[None]] = None
        self._local_logged_in = False
        self._redis_available = False

    async def initialize(self) -> None:
        """Initialize Redis connection."""
        try:
            import redis.asyncio as aioredis

            self._redis = aioredis.from_url(
                self._redis_url,
                encoding="utf-8",
                decode_responses=True,
            )
            # Test connection
            await self._redis.ping()
            self._redis_available = True
            logger.info(
                "[LOGIN_TRACE][DISTRIBUTED] DistributedSessionManager initialized | worker_id={}",
                self._worker_id,
            )
        except ImportError:
            logger.warning("redis package not available, falling back to local-only mode")
            self._redis_available = False
        except Exception as exc:
            logger.warning(f"Redis connection failed, falling back to local-only mode: {exc}")
            self._redis_available = False

    async def ensure_login(
        self,
        login_callback: LoginCallback,
        logout_callback: Optional[LogoutCallback] = None,
    ) -> bool:
        """Ensure SDK is logged in, coordinating with other workers.

        This method implements the following logic:
        1. Check if session already exists in Redis (reuse if valid)
        2. If not, acquire distributed lock
        3. Double-check after acquiring lock
        4. Perform login if needed
        5. Publish session state for other workers

        Args:
            login_callback: Async function that performs the actual SDK login.
            logout_callback: Optional async function for logout (stored for later use).

        Returns:
            True if login successful or session already valid.
        """
        if not self._redis_available:
            # Fallback to local-only mode
            if self._local_logged_in:
                return True
            success = await login_callback()
            self._local_logged_in = success
            return success

        # Step 1: Check existing session
        if await self._check_session_valid():
            logger.debug(f"Reusing existing session | holder={await self._get_session_holder()}")
            return True

        # Step 2: Try to acquire lock
        lock = await self._acquire_lock()
        if lock is None:
            # Another worker is logging in, wait for session
            logger.info("Another worker is logging in, waiting for session...")
            return await self._wait_for_session(timeout=30.0)

        try:
            # Step 3: Double-check after lock acquisition
            if await self._check_session_valid():
                logger.debug("Session became valid while waiting for lock")
                return True

            # Step 4: Perform login
            logger.info(
                "[LOGIN_TRACE][DISTRIBUTED] Acquired login lock, performing login | worker={}",
                self._worker_id,
            )
            success = await login_callback()

            if success:
                # Step 5: Publish session state
                await self._publish_session_state()
                self._is_leader = True
                self._start_heartbeat()
                logger.info(
                    "[LOGIN_TRACE][DISTRIBUTED] Login successful, session published | leader={}",
                    self._worker_id,
                )
            else:
                logger.error("[LOGIN_TRACE][DISTRIBUTED] Login callback returned False")

            return success

        finally:
            await self._release_lock(lock)

    async def _check_session_valid(self) -> bool:
        """Check if shared session in Redis is valid."""
        if not self._redis_available:
            return self._local_logged_in

        try:
            session_data = await self._redis.get(self.SESSION_KEY)
            if not session_data:
                return False

            session = json.loads(session_data)
            if not session.get("logged_in"):
                return False

            # Check heartbeat freshness
            heartbeat_str = session.get("heartbeat", "")
            if not heartbeat_str:
                return False

            heartbeat_time = datetime.fromisoformat(heartbeat_str)
            age = (datetime.now() - heartbeat_time).total_seconds()

            if age > self.SESSION_TTL:
                logger.warning(f"Session expired (age={age:.1f}s > TTL={self.SESSION_TTL}s)")
                return False

            return True

        except Exception as exc:
            logger.warning(f"Failed to check session: {exc}")
            return False

    async def _get_session_holder(self) -> str:
        """Get the worker ID of the current session holder."""
        try:
            session_data = await self._redis.get(self.SESSION_KEY)
            if session_data:
                session = json.loads(session_data)
                return session.get("holder_id", "unknown")
        except Exception:
            pass
        return "unknown"

    async def _acquire_lock(self, timeout: float = 5.0) -> Optional[Any]:
        """Acquire distributed lock using Redis SET NX."""
        if not self._redis_available:
            return True  # Fake lock in local mode

        try:
            # Use Redis SET with NX and EX for atomic lock acquisition
            acquired = await self._redis.set(
                self.LOCK_KEY,
                self._worker_id,
                nx=True,
                ex=self.LOCK_TTL,
            )
            return self._worker_id if acquired else None

        except Exception as exc:
            logger.warning(f"Failed to acquire lock: {exc}")
            return None

    async def _release_lock(self, lock: Any) -> None:
        """Release the distributed lock."""
        if not self._redis_available or lock is None:
            return

        try:
            # Only release if we still hold the lock (避免释放别人的锁)
            current_holder = await self._redis.get(self.LOCK_KEY)
            if current_holder == self._worker_id:
                await self._redis.delete(self.LOCK_KEY)
                logger.debug(f"Lock released | worker={self._worker_id}")
        except Exception as exc:
            logger.warning(f"Failed to release lock: {exc}")

    async def _publish_session_state(self) -> None:
        """Publish session state to Redis."""
        if not self._redis_available:
            self._local_logged_in = True
            return

        try:
            session = {
                "logged_in": True,
                "holder_id": self._worker_id,
                "login_time": datetime.now().isoformat(),
                "heartbeat": datetime.now().isoformat(),
            }
            await self._redis.set(
                self.SESSION_KEY,
                json.dumps(session),
                ex=self.SESSION_TTL * 2,  # Longer TTL, heartbeat refreshes it
            )
        except Exception as exc:
            logger.error(f"Failed to publish session state: {exc}")

    async def _wait_for_session(self, timeout: float = 30.0) -> bool:
        """Wait for another worker to complete login."""
        start = asyncio.get_event_loop().time()

        while asyncio.get_event_loop().time() - start < timeout:
            if await self._check_session_valid():
                logger.info("Session became available")
                return True
            await asyncio.sleep(0.5)

        logger.error(f"Timeout waiting for session ({timeout}s)")
        return False

    def _start_heartbeat(self) -> None:
        """Start heartbeat task to maintain session validity."""
        if self._heartbeat_task is not None:
            return

        async def heartbeat_loop() -> None:
            while self._is_leader:
                try:
                    await self._update_heartbeat()
                    await asyncio.sleep(self.HEARTBEAT_INTERVAL)
                except asyncio.CancelledError:
                    break
                except Exception as exc:
                    logger.warning(f"Heartbeat error: {exc}")
                    await asyncio.sleep(1)

        self._heartbeat_task = asyncio.create_task(heartbeat_loop())

    async def _update_heartbeat(self) -> None:
        """Update heartbeat timestamp in session."""
        if not self._redis_available:
            return

        try:
            session_data = await self._redis.get(self.SESSION_KEY)
            if session_data:
                session = json.loads(session_data)
                session["heartbeat"] = datetime.now().isoformat()
                await self._redis.set(
                    self.SESSION_KEY,
                    json.dumps(session),
                    ex=self.SESSION_TTL * 2,
                )
        except Exception as exc:
            logger.warning(f"Failed to update heartbeat: {exc}")

    async def shutdown(self) -> None:
        """Shutdown the session manager and cleanup resources."""
        self._is_leader = False

        if self._heartbeat_task is not None:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass
            self._heartbeat_task = None

        if self._redis is not None:
            # Clear session if we were the leader
            try:
                current_holder = await self._redis.get(self.SESSION_KEY)
                if current_holder:
                    session = json.loads(current_holder)
                    if session.get("holder_id") == self._worker_id:
                        await self._redis.delete(self.SESSION_KEY)
                        logger.info("Session cleared on shutdown")
            except Exception:
                pass

            await self._redis.close()

        logger.info(f"DistributedSessionManager shutdown | worker={self._worker_id}")

    @property
    def is_leader(self) -> bool:
        """Return whether this worker is the session leader."""
        return self._is_leader

    @property
    def worker_id(self) -> str:
        """Return the worker ID."""
        return self._worker_id
