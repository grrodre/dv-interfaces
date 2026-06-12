"""dv-interfaces — unified interface for solar plant hardware communication."""

from __future__ import annotations

from collections.abc import Mapping
from importlib import import_module
from importlib.metadata import PackageNotFoundError, version
from typing import Any

from ._registry import _REGISTRY
from .base_interface import DVDataset, DVInterfaceBase, DVReadResult
from .detection import DetectionCandidate, detect_interface
from .exceptions import (
    ErrorConnectionDVInterface,
    ErrorDVInterface,
    ErrorLimitingDVInterface,
    ErrorReadDVInterface,
    ErrorTurnOffDVInterface,
    ErrorTurnOnDVInterface,
    ErrorUnsupportedOperationDVInterface,
)
from .modbus import DVInterfaceModbusBase, DVModbusConfiguration
from .utils import stream

try:
    __version__ = version('dv-interfaces')
except PackageNotFoundError:
    __version__ = 'unknown'

__all__ = [
    # Factory
    'get_interface',
    'list_interfaces',
    # Detection
    'detect_interface',
    'DetectionCandidate',
    # Base classes
    'DVInterfaceBase',
    'DVInterfaceModbusBase',
    # Data types
    'DVDataset',
    'DVReadResult',
    'DVModbusConfiguration',
    # Utilities
    'stream',
    # Exceptions
    'ErrorDVInterface',
    'ErrorConnectionDVInterface',
    'ErrorReadDVInterface',
    'ErrorTurnOnDVInterface',
    'ErrorTurnOffDVInterface',
    'ErrorLimitingDVInterface',
    'ErrorUnsupportedOperationDVInterface',
]


def list_interfaces() -> list[dict[str, str]]:
    """Return name and description for every registered interface.

    Useful for populating web app dropdowns or CLI help text.

    Returns:
        [{'name': 'solarlog', 'description': 'SolarLog'}, ...]
    """
    return [
        {'name': name, 'description': entry.description}
        for name, entry in _REGISTRY.items()
    ]


def get_interface(
    name: str,
    host: str,
    port: int = 502,
    modbus_config: DVModbusConfiguration | Mapping[str, Any] | None = None,
) -> DVInterfaceBase:
    """Instantiate and return a driver by name.

    Args:
        name:          Interface name. See list_interfaces() for options.
        host:          Device hostname or IP address.
        port:          TCP port (default 502 for Modbus).
        modbus_config: Modbus client configuration dict or
                       DVModbusConfiguration, validated by Pydantic.
                       Supported keys:
                           slave_id    int   1–247  (default: driver-specific)
                           timeout     float > 0    seconds (default 5.0)
                           max_retries int   ≥ 0    register-level retries (default 0)
                           retry_delay float ≥ 0    seconds between retries (default 0.2)

    Returns:
        A DVInterfaceBase instance for the requested driver.

    Raises:
        ValueError:       Unknown interface name.
        ImportError:      Driver module could not be loaded.
        ValidationError:  modbus_config contains invalid values.

    Example:
        with get_interface('solarlog', '192.168.1.100') as iface:
            result = iface.read_dataset_result()

        with get_interface('solarlog', '192.168.1.100',
                           modbus_config={'slave_id': 3, 'max_retries': 2}) as iface:
            result = iface.read_dataset_result()
    """
    if name not in _REGISTRY:
        available = ', '.join(sorted(_REGISTRY))
        raise ValueError(f'Unknown interface {name!r}. Available: {available}')

    entry = _REGISTRY[name]

    try:
        module = import_module(entry.module)
    except ImportError as exc:
        raise ImportError(f'Failed to load driver module {entry.module!r}') from exc

    driver_class: type[DVInterfaceModbusBase] = getattr(module, entry.class_name)
    return driver_class(host, port, modbus_config=modbus_config)
