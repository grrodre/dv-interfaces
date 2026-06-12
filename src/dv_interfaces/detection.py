from __future__ import annotations

import logging
import socket
from collections.abc import Sequence
from functools import lru_cache
from importlib import import_module
from typing import NamedTuple

from ._registry import _REGISTRY

logger = logging.getLogger(__name__)

_DEFAULT_PORTS: tuple[int, ...] = (502, 5020)


@lru_cache(maxsize=None)
def _load_probe_drivers() -> list:
    drivers = []
    for entry in _REGISTRY.values():
        mod = import_module(entry.module)
        drivers.append(getattr(mod, entry.class_name))
    return drivers


class DetectionCandidate(NamedTuple):
    driver: str
    port: int
    slave_id: int
    confidence: int  # number of probe registers that responded successfully


def _tcp_reachable(host: str, port: int, timeout: float) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def detect_interface(
    host: str,
    ports: Sequence[int] = _DEFAULT_PORTS,
    timeout: float = 2.0,
) -> list[DetectionCandidate]:
    """Probe a host across known ports and return ranked driver candidates.

    Args:
        host:    Device hostname or IP address.
        ports:   TCP ports to try in order. Defaults to (502, 5020).
        timeout: Per-connection timeout in seconds, applied to both the TCP
                 reachability check and each Modbus probe attempt.

    Returns:
        Candidates sorted by confidence descending. Empty list means the host
        is unreachable on all ports or no registered driver matched. Take
        candidates[0] as the suggested default and let the operator confirm.
    """
    candidates: list[DetectionCandidate] = []
    for port in ports:
        if not _tcp_reachable(host, port, timeout):
            logger.debug(f'detect: {host}:{port} not reachable')
            continue
        logger.debug(
            f'detect: {host}:{port} reachable, probing {len(_load_probe_drivers())} drivers'
        )
        for driver_cls in _load_probe_drivers():
            score = driver_cls._probe(host, port, timeout)
            if score > 0:
                logger.debug(
                    f'detect: {host} matched {driver_cls.interface} on port {port}'
                    f' (confidence={score})'
                )
                candidates.append(
                    DetectionCandidate(
                        driver=driver_cls.interface,
                        port=port,
                        slave_id=driver_cls._probe_slave_id,
                        confidence=score,
                    )
                )
    return sorted(candidates, key=lambda c: c.confidence, reverse=True)
