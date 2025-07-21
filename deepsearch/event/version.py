"""
Event Version Management Module

This module provides version management capabilities for events in the DeepSearch platform.
It enables event evolution, backward compatibility, and version tracking.
"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple, Type, TypeVar, Union

from deepsearch.event.engine import Event
from deepsearch.event.schema import BaseEventSchema

# ==============================================================================
# Constants
# ==============================================================================

CURRENT_VERSION = "2.0.0"
MIN_SUPPORTED_VERSION = "1.0.0"
VERSION_HEADER = "_version"
MIGRATION_BATCH_SIZE = 1000
MAX_VERSION_HISTORY = 100

# ==============================================================================
# Type Variables and Logger
# ==============================================================================

logger = logging.getLogger(__name__)
T = TypeVar("T", bound=Event)


# ==============================================================================
# Version Management
# ==============================================================================


class EventVersion:
    """Represents a semantic version for events"""

    def __init__(self, version_string: str):
        """Initialize from version string (e.g., '1.2.3')"""
        parts = version_string.split('.')
        if len(parts) != 3:
            raise ValueError(f"Invalid version format: {version_string}")

        try:
            self.major = int(parts[0])
            self.minor = int(parts[1])
            self.patch = int(parts[2])
        except ValueError:
            raise ValueError(f"Invalid version format: {version_string}")

    def __str__(self) -> str:
        return f"{self.major}.{self.minor}.{self.patch}"

    def __repr__(self) -> str:
        return f"EventVersion('{self}')"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, EventVersion):
            return NotImplemented
        return (self.major, self.minor, self.patch) == (other.major, other.minor, other.patch)

    def __lt__(self, other: EventVersion) -> bool:
        return (self.major, self.minor, self.patch) < (other.major, other.minor, other.patch)

    def __le__(self, other: EventVersion) -> bool:
        return self == other or self < other

    def __hash__(self) -> int:
        return hash((self.major, self.minor, self.patch))

    def is_compatible_with(self, other: EventVersion) -> bool:
        """Check if this version is compatible with another (same major version)"""
        return self.major == other.major

    def bump_major(self) -> EventVersion:
        """Create new version with incremented major number"""
        return EventVersion(f"{self.major + 1}.0.0")

    def bump_minor(self) -> EventVersion:
        """Create new version with incremented minor number"""
        return EventVersion(f"{self.major}.{self.minor + 1}.0")

    def bump_patch(self) -> EventVersion:
        """Create new version with incremented patch number"""
        return EventVersion(f"{self.major}.{self.minor}.{self.patch + 1}")


# ==============================================================================
# Version Registry
# ==============================================================================


@dataclass
class VersionInfo:
    """Information about an event version"""
    version: EventVersion
    schema: Optional[Type[BaseEventSchema]]
    deprecated: bool = False
    deprecated_since: Optional[EventVersion] = None
    removal_version: Optional[EventVersion] = None
    migration_notes: str = ""


class VersionRegistry:
    """Registry for event versions and their schemas"""

    def __init__(self):
        self._versions: Dict[str, Dict[EventVersion, VersionInfo]] = {}
        self._current_versions: Dict[str, EventVersion] = {}
        self._migration_paths: Dict[str, Dict[Tuple[EventVersion, EventVersion], List[EventVersion]]] = {}

    def register_version(
            self,
            event_type: str,
            version: Union[str, EventVersion],
            schema: Optional[Type[BaseEventSchema]] = None,
            is_current: bool = False
    ) -> None:
        """Register a version for an event type"""
        if isinstance(version, str):
            version = EventVersion(version)

        if event_type not in self._versions:
            self._versions[event_type] = {}

        self._versions[event_type][version] = VersionInfo(
            version=version,
            schema=schema
        )

        if is_current:
            self._current_versions[event_type] = version

        logger.info(f"Registered version {version} for event type: {event_type}")

    def deprecate_version(
            self,
            event_type: str,
            version: Union[str, EventVersion],
            removal_version: Optional[Union[str, EventVersion]] = None,
            notes: str = ""
    ) -> None:
        """Mark a version as deprecated"""
        if isinstance(version, str):
            version = EventVersion(version)
        if isinstance(removal_version, str):
            removal_version = EventVersion(removal_version)

        if event_type not in self._versions or version not in self._versions[event_type]:
            raise ValueError(f"Version {version} not found for event type {event_type}")

        info = self._versions[event_type][version]
        info.deprecated = True
        info.deprecated_since = self._current_versions.get(event_type)
        info.removal_version = removal_version
        info.migration_notes = notes

        logger.warning(f"Deprecated version {version} for event type: {event_type}")

    def get_current_version(self, event_type: str) -> Optional[EventVersion]:
        """Get current version for an event type"""
        return self._current_versions.get(event_type)

    def get_version_info(self, event_type: str, version: Union[str, EventVersion]) -> Optional[VersionInfo]:
        """Get version information"""
        if isinstance(version, str):
            version = EventVersion(version)

        return self._versions.get(event_type, {}).get(version)

    def is_supported(self, event_type: str, version: Union[str, EventVersion]) -> bool:
        """Check if a version is still supported"""
        info = self.get_version_info(event_type, version)
        return info is not None and not info.deprecated

    def get_migration_path(
            self,
            event_type: str,
            from_version: EventVersion,
            to_version: EventVersion
    ) -> List[EventVersion]:
        """Get migration path between versions"""
        if event_type not in self._migration_paths:
            self._build_migration_paths(event_type)

        key = (from_version, to_version)
        return self._migration_paths[event_type].get(key, [])

    def _build_migration_paths(self, event_type: str) -> None:
        """Build migration paths for an event type"""
        if event_type not in self._versions:
            return

        versions = sorted(self._versions[event_type].keys())
        paths = {}

        # Build direct paths
        for i, v1 in enumerate(versions):
            for v2 in versions[i + 1:]:
                paths[(v1, v2)] = [v1, v2]

        self._migration_paths[event_type] = paths


# ==============================================================================
# Version Migrators
# ==============================================================================


class VersionMigrator(ABC):
    """Base class for version migrations"""

    @property
    @abstractmethod
    def event_type(self) -> str:
        """Event type this migrator handles"""
        pass

    @property
    @abstractmethod
    def from_version(self) -> EventVersion:
        """Source version"""
        pass

    @property
    @abstractmethod
    def to_version(self) -> EventVersion:
        """Target version"""
        pass

    @abstractmethod
    def migrate(self, event_data: Dict[str, Any]) -> Dict[str, Any]:
        """Migrate event data from old version to new version"""
        pass

    def can_migrate(self, event_type: str, from_version: EventVersion) -> bool:
        """Check if this migrator can handle the migration"""
        return (
                event_type == self.event_type and
                from_version == self.from_version
        )


class CompositeMigrator(VersionMigrator):
    """Migrator that chains multiple migrations"""

    def __init__(self, migrators: List[VersionMigrator]):
        self._migrators = migrators
        if not migrators:
            raise ValueError("At least one migrator required")

    @property
    def event_type(self) -> str:
        return self._migrators[0].event_type

    @property
    def from_version(self) -> EventVersion:
        return self._migrators[0].from_version

    @property
    def to_version(self) -> EventVersion:
        return self._migrators[-1].to_version

    def migrate(self, event_data: Dict[str, Any]) -> Dict[str, Any]:
        """Apply migrations in sequence"""
        result = event_data
        for migrator in self._migrators:
            result = migrator.migrate(result)
        return result


# ==============================================================================
# Version Migration Registry
# ==============================================================================


class MigrationRegistry:
    """Registry for version migrations"""

    def __init__(self):
        self._migrators: Dict[str, Dict[Tuple[EventVersion, EventVersion], VersionMigrator]] = {}

    def register_migrator(self, migrator: VersionMigrator) -> None:
        """Register a version migrator"""
        event_type = migrator.event_type
        key = (migrator.from_version, migrator.to_version)

        if event_type not in self._migrators:
            self._migrators[event_type] = {}

        self._migrators[event_type][key] = migrator
        logger.info(f"Registered migrator for {event_type}: {key[0]} -> {key[1]}")

    def get_migrator(
            self,
            event_type: str,
            from_version: EventVersion,
            to_version: EventVersion
    ) -> Optional[VersionMigrator]:
        """Get migrator for specific versions"""
        if event_type not in self._migrators:
            return None

        return self._migrators[event_type].get((from_version, to_version))

    def build_migration_chain(
            self,
            event_type: str,
            from_version: EventVersion,
            to_version: EventVersion,
            version_registry: VersionRegistry
    ) -> Optional[VersionMigrator]:
        """Build a chain of migrators for multi-step migration"""
        path = version_registry.get_migration_path(event_type, from_version, to_version)
        if not path or len(path) < 2:
            return None

        migrators = []
        for i in range(len(path) - 1):
            migrator = self.get_migrator(event_type, path[i], path[i + 1])
            if not migrator:
                logger.error(f"Missing migrator for {event_type}: {path[i]} -> {path[i + 1]}")
                return None
            migrators.append(migrator)

        if len(migrators) == 1:
            return migrators[0]
        return CompositeMigrator(migrators)


# ==============================================================================
# Versioned Event Wrapper
# ==============================================================================


class VersionedEvent(Event):
    """Event with version information"""

    def __init__(
            self,
            type: str,
            data: Any,
            version: Optional[Union[str, EventVersion]] = None,
            **kwargs
    ):
        super().__init__(type, data, **kwargs)

        if version is None:
            version = version_registry.get_current_version(type) or EventVersion(CURRENT_VERSION)
        elif isinstance(version, str):
            version = EventVersion(version)

        self.version = version

        # Add version to data if not present
        if isinstance(self.data, dict):
            self.data[VERSION_HEADER] = str(self.version)

    @classmethod
    def from_event(cls, event: Event) -> VersionedEvent:
        """Create versioned event from regular event"""
        version = None

        # Extract version from data if present
        if isinstance(event.data, dict) and VERSION_HEADER in event.data:
            version = event.data[VERSION_HEADER]

        return cls(
            type=event.type,
            data=event.data,
            version=version,
            timestamp=event.timestamp
        )

    def migrate_to(self, target_version: Union[str, EventVersion]) -> VersionedEvent:
        """Migrate event to a different version"""
        if isinstance(target_version, str):
            target_version = EventVersion(target_version)

        if self.version == target_version:
            return self

        # Get migrator
        migrator = migration_registry.build_migration_chain(
            self.type,
            self.version,
            target_version,
            version_registry
        )

        if not migrator:
            raise ValueError(f"No migration path from {self.version} to {target_version}")

        # Migrate data
        migrated_data = migrator.migrate(self.data.copy())

        return VersionedEvent(
            type=self.type,
            data=migrated_data,
            version=target_version,
            timestamp=self.timestamp
        )

    def is_current_version(self) -> bool:
        """Check if event is at current version"""
        current = version_registry.get_current_version(self.type)
        return current is not None and self.version == current

    def is_deprecated(self) -> bool:
        """Check if event version is deprecated"""
        info = version_registry.get_version_info(self.type, self.version)
        return info is not None and info.deprecated


# ==============================================================================
# Version Compatibility Checker
# ==============================================================================


class CompatibilityChecker:
    """Checks version compatibility between components"""

    def __init__(self):
        self._component_versions: Dict[str, EventVersion] = {}

    def register_component(self, name: str, version: Union[str, EventVersion]) -> None:
        """Register a component and its version"""
        if isinstance(version, str):
            version = EventVersion(version)
        self._component_versions[name] = version

    def check_compatibility(self, event_type: str, event_version: EventVersion) -> List[str]:
        """Check which components are compatible with an event version"""
        compatible = []

        for component, version in self._component_versions.items():
            if event_version.is_compatible_with(version):
                compatible.append(component)

        return compatible

    def get_compatibility_matrix(self) -> Dict[str, Dict[str, bool]]:
        """Get full compatibility matrix"""
        matrix = {}

        for comp1, ver1 in self._component_versions.items():
            matrix[comp1] = {}
            for comp2, ver2 in self._component_versions.items():
                matrix[comp1][comp2] = ver1.is_compatible_with(ver2)

        return matrix


# ==============================================================================
# Example Migrators
# ==============================================================================


class TickV1ToV2Migrator(VersionMigrator):
    """Example migrator for tick events from v1 to v2"""

    @property
    def event_type(self) -> str:
        return "TICK"

    @property
    def from_version(self) -> EventVersion:
        return EventVersion("1.0.0")

    @property
    def to_version(self) -> EventVersion:
        return EventVersion("2.0.0")

    def migrate(self, event_data: Dict[str, Any]) -> Dict[str, Any]:
        """Migrate tick data from v1 to v2"""
        migrated = event_data.copy()

        # Example: v2 splits price into bid/ask
        if "price" in migrated:
            migrated["bid_price"] = migrated["price"]
            migrated["ask_price"] = migrated["price"]
            del migrated["price"]

        # Update version
        migrated[VERSION_HEADER] = str(self.to_version)

        return migrated


# ==============================================================================
# Global Registry Instances
# ==============================================================================

# Create global registries
version_registry = VersionRegistry()
migration_registry = MigrationRegistry()
compatibility_checker = CompatibilityChecker()

# Register example versions
version_registry.register_version("TICK", "1.0.0")
version_registry.register_version("TICK", "2.0.0", is_current=True)
version_registry.register_version("ORDER", "1.0.0", is_current=True)
version_registry.register_version("TRADE", "1.0.0", is_current=True)

# Register example migrator
migration_registry.register_migrator(TickV1ToV2Migrator())


# ==============================================================================
# Version Management Utilities
# ==============================================================================


def ensure_current_version(event: Event) -> Event:
    """Ensure event is at current version, migrating if necessary"""
    versioned = VersionedEvent.from_event(event)

    if not versioned.is_current_version():
        current = version_registry.get_current_version(event.type)
        if current:
            versioned = versioned.migrate_to(current)

    return versioned


def check_version_compatibility(event: Event) -> Dict[str, Any]:
    """Check version compatibility for an event"""
    versioned = VersionedEvent.from_event(event)

    return {
        "version": str(versioned.version),
        "is_current": versioned.is_current_version(),
        "is_deprecated": versioned.is_deprecated(),
        "compatible_components": compatibility_checker.check_compatibility(
            event.type,
            versioned.version
        )
    }


# ==============================================================================
# Module Summary
# ==============================================================================
"""
Event Version Management System

This module provides comprehensive version management for events:

1. Version Representation:
   - EventVersion: Semantic versioning (major.minor.patch)
   - Version comparison and compatibility checking
   - Version bumping utilities

2. Version Registry:
   - Track versions for each event type
   - Current version management
   - Deprecation tracking
   - Migration path calculation

3. Version Migration:
   - VersionMigrator base class
   - CompositeMigrator for multi-step migrations
   - Migration registry and chain building

4. Versioned Events:
   - VersionedEvent wrapper with version metadata
   - Automatic version extraction and injection
   - Migration methods

5. Compatibility Checking:
   - Component version tracking
   - Compatibility matrix generation
   - Cross-component compatibility validation

Usage Example:
    from deepsearch.event.version import VersionedEvent, version_registry
    
    # Create versioned event
    event = VersionedEvent(
        type="TICK",
        data={"symbol": "BTCUSDT", "price": 50000},
        version="1.0.0"
    )
    
    # Migrate to current version
    current_event = event.migrate_to(version_registry.get_current_version("TICK"))
    
    # Check compatibility
    if event.is_deprecated():
        logger.warning("Using deprecated event version")
"""
