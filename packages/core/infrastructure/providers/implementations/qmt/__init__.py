"""QMT data provider implementation.

Exports:
    MiniQMTWorkerPlugin: Dask Worker Plugin for MiniQMT Actor
    register_miniqmt_plugin: Convenience function to register the plugin
"""

from .dask_plugin import MiniQMTWorkerPlugin, register_miniqmt_plugin

__all__ = ["MiniQMTWorkerPlugin", "register_miniqmt_plugin"]
