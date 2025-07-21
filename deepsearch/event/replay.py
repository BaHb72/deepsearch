"""
Event Replay Module

This module provides event replay functionality for the DeepSearch platform,
enabling historical event playback, backtesting, and system recovery.
"""
from __future__ import annotations

import json
import logging
import threading
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple, Union

from deepsearch.event.engine import Event, EventEngine
from deepsearch.storage.timeseries import RedisTimeSeriesStorage

# ==============================================================================
# Constants
# ==============================================================================

DEFAULT_REPLAY_SPEED = 1.0  # 1x real-time
MAX_REPLAY_SPEED = 1000.0  # 1000x real-time
MIN_REPLAY_SPEED = 0.1  # 0.1x real-time
DEFAULT_BATCH_SIZE = 1000
DEFAULT_BUFFER_SIZE = 10000

# ==============================================================================
# Type Definitions and Logger
# ==============================================================================

logger = logging.getLogger(__name__)


class ReplayMode(str, Enum):
    """Event replay modes"""
    REALTIME = "realtime"  # Replay at original speed
    FAST = "fast"  # Replay as fast as possible
    STEPPED = "stepped"  # Replay step by step


class ReplayStatus(str, Enum):
    """Replay session status"""
    IDLE = "idle"
    PLAYING = "playing"
    PAUSED = "paused"
    COMPLETED = "completed"
    ERROR = "error"


# ==============================================================================
# Event Source Interface
# ==============================================================================


class EventSource(ABC):
    """Abstract base class for event sources"""

    @abstractmethod
    def get_events(
            self,
            start_time: Optional[float] = None,
            end_time: Optional[float] = None,
            event_types: Optional[List[str]] = None,
            limit: Optional[int] = None
    ) -> List[Event]:
        """Retrieve events from the source"""
        pass

    @abstractmethod
    def get_event_count(
            self,
            start_time: Optional[float] = None,
            end_time: Optional[float] = None,
            event_types: Optional[List[str]] = None
    ) -> int:
        """Get count of events matching criteria"""
        pass

    @abstractmethod
    def get_time_range(self) -> Tuple[Optional[float], Optional[float]]:
        """Get available time range (start, end)"""
        pass


class FileEventSource(EventSource):
    """Event source that reads from files"""

    def __init__(self, file_path: Union[str, Path]):
        self.file_path = Path(file_path)
        self._events: List[Event] = []
        self._load_events()

    def _load_events(self) -> None:
        """Load events from file"""
        if not self.file_path.exists():
            raise FileNotFoundError(f"Event file not found: {self.file_path}")

        try:
            with open(self.file_path, 'r') as f:
                if self.file_path.suffix == '.json':
                    data = json.load(f)
                    for event_data in data:
                        event = Event(
                            type=event_data['type'],
                            data=event_data.get('data', {}),
                            ts=event_data.get('ts', time.time())
                        )
                        self._events.append(event)
                else:
                    # Assume line-delimited JSON
                    for line in f:
                        event_data = json.loads(line.strip())
                        event = Event(
                            type=event_data['type'],
                            data=event_data.get('data', {}),
                            ts=event_data.get('ts', time.time())
                        )
                        self._events.append(event)

            # Sort events by timestamp
            self._events.sort(key=lambda e: e.ts)
            logger.info(f"Loaded {len(self._events)} events from {self.file_path}")

        except Exception as e:
            logger.error(f"Failed to load events from {self.file_path}: {e}")
            raise

    def get_events(
            self,
            start_time: Optional[float] = None,
            end_time: Optional[float] = None,
            event_types: Optional[List[str]] = None,
            limit: Optional[int] = None
    ) -> List[Event]:
        """Get events matching criteria"""
        events = self._events

        # Filter by time range
        if start_time is not None:
            events = [e for e in events if e.ts >= start_time]
        if end_time is not None:
            events = [e for e in events if e.ts <= end_time]

        # Filter by event types
        if event_types:
            event_types_set = set(event_types)
            events = [e for e in events if e.type in event_types_set]

        # Apply limit
        if limit and len(events) > limit:
            events = events[:limit]

        return events

    def get_event_count(
            self,
            start_time: Optional[float] = None,
            end_time: Optional[float] = None,
            event_types: Optional[List[str]] = None
    ) -> int:
        """Get count of events matching criteria"""
        return len(self.get_events(start_time, end_time, event_types))

    def get_time_range(self) -> Tuple[Optional[float], Optional[float]]:
        """Get available time range"""
        if not self._events:
            return None, None
        return self._events[0].ts, self._events[-1].ts


class TimeSeriesEventSource(EventSource):
    """Event source that reads from TimeSeries storage"""

    def __init__(self, storage: RedisTimeSeriesStorage, topic: str):
        self.storage = storage
        self.topic = topic

    def get_events(
            self,
            start_time: Optional[float] = None,
            end_time: Optional[float] = None,
            event_types: Optional[List[str]] = None,
            limit: Optional[int] = None
    ) -> List[Event]:
        """Get events from TimeSeries"""
        # Query events from storage
        events_data = self.storage.query_events(
            topic=self.topic,
            event_type=None,  # We'll filter after retrieval
            start_time=start_time,
            end_time=end_time,
            limit=limit
        )

        # Convert to Event objects
        events = []
        for data in events_data:
            event = Event(
                type=data.get('type', 'UNKNOWN'),
                data=data.get('data', {}),
                ts=data.get('timestamp', time.time())
            )
            events.append(event)

        # Filter by event types if specified
        if event_types:
            event_types_set = set(event_types)
            events = [e for e in events if e.type in event_types_set]

        return events

    def get_event_count(
            self,
            start_time: Optional[float] = None,
            end_time: Optional[float] = None,
            event_types: Optional[List[str]] = None
    ) -> int:
        """Get count of events"""
        # For efficiency, we might want to implement a count method in storage
        return len(self.get_events(start_time, end_time, event_types))

    def get_time_range(self) -> Tuple[Optional[float], Optional[float]]:
        """Get available time range"""
        # Query storage for time range
        stats = self.storage.get_stats()
        topic_stats = stats.get('topics', {}).get(self.topic, {})

        if not topic_stats:
            return None, None

        return topic_stats.get('first_timestamp'), topic_stats.get('last_timestamp')


# ==============================================================================
# Event Replay Engine
# ==============================================================================


@dataclass
class ReplayConfig:
    """Configuration for replay session"""
    mode: ReplayMode = ReplayMode.REALTIME
    speed: float = DEFAULT_REPLAY_SPEED
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    event_types: Optional[List[str]] = None
    loop: bool = False
    batch_size: int = DEFAULT_BATCH_SIZE
    buffer_size: int = DEFAULT_BUFFER_SIZE


@dataclass
class ReplayStats:
    """Statistics for replay session"""
    total_events: int = 0
    processed_events: int = 0
    skipped_events: int = 0
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    elapsed_time: float = 0.0
    current_position: float = 0.0


class EventReplayEngine:
    """Engine for replaying historical events"""

    def __init__(
            self,
            event_source: EventSource,
            event_engine: EventEngine,
            config: Optional[ReplayConfig] = None
    ):
        self.event_source = event_source
        self.event_engine = event_engine
        self.config = config or ReplayConfig()

        # State management
        self._status = ReplayStatus.IDLE
        self._stats = ReplayStats()
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._pause_event = threading.Event()
        self._pause_event.set()  # Start unpaused

        # Event filters
        self._event_filters: List[Callable[[Event], bool]] = []

        # Progress callbacks
        self._progress_callbacks: List[Callable[[ReplayStats], None]] = []

        # Buffer for events
        self._event_buffer: List[Event] = []
        self._buffer_lock = threading.Lock()

    def add_filter(self, filter_func: Callable[[Event], bool]) -> None:
        """Add event filter function"""
        self._event_filters.append(filter_func)

    def remove_filter(self, filter_func: Callable[[Event], bool]) -> None:
        """Remove event filter function"""
        if filter_func in self._event_filters:
            self._event_filters.remove(filter_func)

    def add_progress_callback(self, callback: Callable[[ReplayStats], None]) -> None:
        """Add progress callback"""
        self._progress_callbacks.append(callback)

    def remove_progress_callback(self, callback: Callable[[ReplayStats], None]) -> None:
        """Remove progress callback"""
        if callback in self._progress_callbacks:
            self._progress_callbacks.remove(callback)

    def start(self) -> None:
        """Start replay session"""
        if self._status == ReplayStatus.PLAYING:
            logger.warning("Replay already in progress")
            return

        self._status = ReplayStatus.PLAYING
        self._stop_event.clear()
        self._pause_event.set()

        # Reset stats
        self._stats = ReplayStats()

        # Start replay thread
        self._thread = threading.Thread(target=self._replay_loop, daemon=True)
        self._thread.start()

        logger.info("Replay session started")

    def pause(self) -> None:
        """Pause replay"""
        if self._status == ReplayStatus.PLAYING:
            self._pause_event.clear()
            self._status = ReplayStatus.PAUSED
            logger.info("Replay paused")

    def resume(self) -> None:
        """Resume replay"""
        if self._status == ReplayStatus.PAUSED:
            self._pause_event.set()
            self._status = ReplayStatus.PLAYING
            logger.info("Replay resumed")

    def stop(self) -> None:
        """Stop replay"""
        if self._status in (ReplayStatus.PLAYING, ReplayStatus.PAUSED):
            self._stop_event.set()
            self._pause_event.set()  # Unpause if paused

            if self._thread:
                self._thread.join(timeout=5.0)

            self._status = ReplayStatus.IDLE
            logger.info("Replay stopped")

    def get_status(self) -> ReplayStatus:
        """Get current replay status"""
        return self._status

    def get_stats(self) -> ReplayStats:
        """Get replay statistics"""
        return self._stats

    def set_speed(self, speed: float) -> None:
        """Set replay speed"""
        if MIN_REPLAY_SPEED <= speed <= MAX_REPLAY_SPEED:
            self.config.speed = speed
            logger.info(f"Replay speed set to {speed}x")
        else:
            raise ValueError(f"Speed must be between {MIN_REPLAY_SPEED} and {MAX_REPLAY_SPEED}")

    def seek(self, timestamp: float) -> None:
        """Seek to specific timestamp"""
        # This would require more complex implementation
        # For now, we'd need to restart replay from the new position
        logger.warning("Seek functionality not fully implemented")

    def _replay_loop(self) -> None:
        """Main replay loop"""
        try:
            # Get events to replay
            events = self._load_events()
            if not events:
                logger.warning("No events to replay")
                self._status = ReplayStatus.COMPLETED
                return

            self._stats.total_events = len(events)
            self._stats.start_time = time.time()

            # Replay events
            if self.config.mode == ReplayMode.REALTIME:
                self._replay_realtime(events)
            elif self.config.mode == ReplayMode.FAST:
                self._replay_fast(events)
            elif self.config.mode == ReplayMode.STEPPED:
                self._replay_stepped(events)

            # Handle loop mode
            if self.config.loop and not self._stop_event.is_set():
                logger.info("Looping replay")
                self._replay_loop()
            else:
                self._status = ReplayStatus.COMPLETED

        except Exception as e:
            logger.error(f"Replay error: {e}")
            self._status = ReplayStatus.ERROR

    def _load_events(self) -> List[Event]:
        """Load events from source"""
        events = self.event_source.get_events(
            start_time=self.config.start_time,
            end_time=self.config.end_time,
            event_types=self.config.event_types
        )

        # Apply filters
        for filter_func in self._event_filters:
            events = [e for e in events if filter_func(e)]

        return events

    def _replay_realtime(self, events: List[Event]) -> None:
        """Replay events at original timing"""
        if not events:
            return

        base_time = events[0].ts
        start_real_time = time.time()

        for i, event in enumerate(events):
            if self._stop_event.is_set():
                break

            # Wait for unpause
            self._pause_event.wait()

            # Calculate wait time
            event_offset = event.ts - base_time
            target_real_time = start_real_time + (event_offset / self.config.speed)
            wait_time = target_real_time - time.time()

            if wait_time > 0:
                time.sleep(wait_time)

            # Dispatch event
            self._dispatch_event(event)

            # Update stats
            self._update_stats(i + 1, event.ts)

    def _replay_fast(self, events: List[Event]) -> None:
        """Replay events as fast as possible"""
        for i, event in enumerate(events):
            if self._stop_event.is_set():
                break

            # Wait for unpause
            self._pause_event.wait()

            # Dispatch event
            self._dispatch_event(event)

            # Update stats
            self._update_stats(i + 1, event.ts)

    def _replay_stepped(self, events: List[Event]) -> None:
        """Replay events step by step (requires manual progression)"""
        # This mode would require additional control methods
        logger.warning("Stepped mode not fully implemented")
        self._replay_fast(events)  # Fallback to fast mode

    def _dispatch_event(self, event: Event) -> None:
        """Dispatch event to engine"""
        try:
            success = self.event_engine.put(event)
            if not success:
                self._stats.skipped_events += 1
        except Exception as e:
            logger.error(f"Failed to dispatch event: {e}")
            self._stats.skipped_events += 1

    def _update_stats(self, processed: int, current_timestamp: float) -> None:
        """Update replay statistics"""
        self._stats.processed_events = processed
        self._stats.current_position = current_timestamp
        self._stats.elapsed_time = time.time() - self._stats.start_time

        # Notify callbacks
        for callback in self._progress_callbacks:
            try:
                callback(self._stats)
            except Exception as e:
                logger.error(f"Progress callback error: {e}")


# ==============================================================================
# Replay Session Manager
# ==============================================================================


class ReplaySessionManager:
    """Manages multiple replay sessions"""

    def __init__(self):
        self._sessions: Dict[str, EventReplayEngine] = {}
        self._lock = threading.Lock()

    def create_session(
            self,
            session_id: str,
            event_source: EventSource,
            event_engine: EventEngine,
            config: Optional[ReplayConfig] = None
    ) -> EventReplayEngine:
        """Create a new replay session"""
        with self._lock:
            if session_id in self._sessions:
                raise ValueError(f"Session {session_id} already exists")

            session = EventReplayEngine(event_source, event_engine, config)
            self._sessions[session_id] = session

            logger.info(f"Created replay session: {session_id}")
            return session

    def get_session(self, session_id: str) -> Optional[EventReplayEngine]:
        """Get existing session"""
        return self._sessions.get(session_id)

    def remove_session(self, session_id: str) -> None:
        """Remove session"""
        with self._lock:
            if session_id in self._sessions:
                session = self._sessions[session_id]
                session.stop()
                del self._sessions[session_id]
                logger.info(f"Removed replay session: {session_id}")

    def list_sessions(self) -> List[Tuple[str, ReplayStatus]]:
        """List all sessions with their status"""
        with self._lock:
            return [(sid, session.get_status()) for sid, session in self._sessions.items()]

    def stop_all(self) -> None:
        """Stop all sessions"""
        with self._lock:
            for session in self._sessions.values():
                session.stop()


# ==============================================================================
# Module Summary
# ==============================================================================
"""
Event Replay Module

This module provides comprehensive event replay functionality:

1. Event Sources:
   - EventSource: Abstract interface for event sources
   - FileEventSource: Replay from JSON files
   - TimeSeriesEventSource: Replay from Redis TimeSeries

2. Replay Modes:
   - REALTIME: Replay at original speed (with speed multiplier)
   - FAST: Replay as fast as possible
   - STEPPED: Manual step-by-step replay

3. Replay Engine:
   - Configurable replay speed and filtering
   - Progress tracking and callbacks
   - Pause/resume/stop controls
   - Loop mode for continuous replay

4. Session Management:
   - Multiple concurrent replay sessions
   - Session lifecycle management

Usage Example:
    from deepsearch.event.replay import EventReplayEngine, FileEventSource, ReplayConfig
    
    # Create event source
    source = FileEventSource("historical_events.json")
    
    # Configure replay
    config = ReplayConfig(
        mode=ReplayMode.REALTIME,
        speed=2.0,  # 2x speed
        start_time=start_timestamp,
        event_types=["TICK", "TRADE"]
    )
    
    # Create replay engine
    replay = EventReplayEngine(source, event_engine, config)
    
    # Add progress monitoring
    def on_progress(stats: ReplayStats):
        print(f"Progress: {stats.processed_events}/{stats.total_events}")
    
    replay.add_progress_callback(on_progress)
    
    # Start replay
    replay.start()
"""
