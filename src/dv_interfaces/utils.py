"""Utilities for streaming dv-interfaces drivers."""

from __future__ import annotations

import time
from collections.abc import Generator

from .base_interface import DVInterfaceBase, DVReadResult


def stream(
    iface: DVInterfaceBase,
    interval_s: float = 0.0,
) -> Generator[DVReadResult | Exception, None, None]:
    """Yield DVReadResult continuously from iface.

    On read failure, the exception is yielded instead of raised so the stream
    never stops. Callers check isinstance(result, Exception) to detect errors.

    Args:
        iface:       Any DVInterfaceBase driver (connected or not — _ensure_connected
                     runs automatically before each read).
        interval_s:  Seconds to wait between reads. 0 = as fast as possible.

    Example:
        for result in stream(iface, interval_s=60):
            if isinstance(result, Exception):
                logger.error('read failed: %s', result)
                continue
            db.save(result.to_dict())

    Finite reads with itertools.islice:
        from itertools import islice
        ten_readings = list(islice(stream(iface, interval_s=5), 10))

    Pandas DataFrame:
        import pandas as pd
        from itertools import islice
        df = pd.DataFrame(
            r.to_dict() for r in islice(stream(iface, interval_s=60), 100)
            if not isinstance(r, Exception)
        )
    """
    while True:
        try:
            yield iface.read_dataset_result()
        except Exception as exc:
            yield exc
        if interval_s > 0:
            time.sleep(interval_s)
