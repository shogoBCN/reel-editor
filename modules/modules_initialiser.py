"""
Video-editor module manager (singleton).

Lazy-loads shared instances so pipelines never construct a second ConfigStore.
Usage matches Locaria repos:

    from modules.modules_initialiser import get_module
    config_store = get_module("config_store")

Supported names: ``config_store``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal, overload

if TYPE_CHECKING:
    from config.config_store import ConfigStore


class ModuleInitialiser:
    """Singleton that owns lazily created shared modules."""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        if hasattr(self, "_initialized") and self._initialized:
            return
        self._initialized = True
        self._config_store = None

    def get_config_store(self):
        """Get or create the ConfigStore. Returns the cached instance if already loaded."""
        if self._config_store is None:
            from config.config_store import ConfigStore

            self._config_store = ConfigStore()
        return self._config_store


_module_initialiser: ModuleInitialiser | None = None


def get_module_initialiser() -> ModuleInitialiser:
    """Get the singleton ModuleInitialiser instance."""
    global _module_initialiser
    if _module_initialiser is None:
        _module_initialiser = ModuleInitialiser()
    return _module_initialiser


@overload
def get_module(name: Literal["config_store"]) -> "ConfigStore": ...


def get_module(name: str, **kwargs):
    """
    Get a module by name. Import once, call with the module you need.

    Args:
        name: Currently ``config_store``. Extra names can be added without
            changing call sites.

    Returns:
        The requested module instance (singleton, lazy-loaded).
    """
    app = get_module_initialiser()
    if name == "config_store":
        return app.get_config_store()
    raise ValueError(
        f"Unknown module {name!r}. Supported: 'config_store'."
    )
