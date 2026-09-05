"""
Lazy singleton for shared modules (Locaria ``get_module`` pattern).

Pipelines must not construct a second ``ConfigStore``: each instance would
re-insert ``sys.path`` and disagree about canvas constants. This file is the
single integration point — add new shared clients here, not in pipeline files.

Usage:

    from modules.modules_initialiser import get_module
    config_store = get_module("config_store")

Supported names: ``config_store``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal, overload

if TYPE_CHECKING:
    from config.config_store import ConfigStore


class ModuleInitialiser:
    """Owns lazily created shared module instances for the whole process."""

    _instance = None

    def __new__(cls):
        """Return the process-wide instance (true singleton).

        Returns:
            The one ``ModuleInitialiser`` for this Python process.
        """
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        """Allocate cache slots once. Later ``__init__`` calls are no-ops.

        ``__new__`` can return an existing instance, so we guard with
        ``_initialized`` to avoid wiping a live ``ConfigStore``.
        """
        if hasattr(self, "_initialized") and self._initialized:
            return
        self._initialized = True
        self._config_store = None

    def get_config_store(self):
        """Create ``ConfigStore`` on first use and reuse it forever after.

        Returns:
            The cached ``ConfigStore``.
        """
        if self._config_store is None:
            from config.config_store import ConfigStore

            self._config_store = ConfigStore()
        return self._config_store


_module_initialiser: ModuleInitialiser | None = None


def get_module_initialiser() -> ModuleInitialiser:
    """Return the process-wide ``ModuleInitialiser``, creating it if needed.

    Returns:
        Singleton initialiser used by ``get_module``.
    """
    global _module_initialiser
    if _module_initialiser is None:
        _module_initialiser = ModuleInitialiser()
    return _module_initialiser


@overload
def get_module(name: Literal["config_store"]) -> "ConfigStore": ...


def get_module(name: str, **kwargs):
    """Fetch a shared module by name (Locaria one-liner).

    Args:
        name: Currently only ``config_store``. Extra names can be added without
            changing call sites.
        **kwargs: Reserved for future modules that need construction args
            (e.g. a BigQuery client with ``project_id``).

    Returns:
        The requested singleton instance.

    Raises:
        ValueError: ``name`` is not a registered module.
    """
    initialiser = get_module_initialiser()
    if name == "config_store":
        return initialiser.get_config_store()
    raise ValueError(
        f"Unknown module {name!r}. Supported: 'config_store'."
    )
