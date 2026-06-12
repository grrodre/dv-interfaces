import logging
import time
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any, ClassVar

from pydantic import BaseModel, ConfigDict, Field, field_serializer

logger = logging.getLogger(__name__)


class DVDataset(BaseModel):
    model_config = ConfigDict(frozen=True)

    production: int = Field(description='Realtime production in W')
    consumption: int = Field(description='Realtime consumption in W')
    grid_feed: int = Field(
        description='Grid exchange in W — positive = feeding, negative = consuming'
    )
    limitation_nb_percent: float | None = Field(
        None, description='Netzbetreiber limitation in %'
    )
    limitation_nb_w: float | None = Field(
        None, description='Netzbetreiber limitation in W'
    )
    limitation_dv_percent: float | None = Field(
        None, description='Direktvermarkter limitation in %'
    )
    limitation_dv_w: float | None = Field(
        None, description='Direktvermarkter limitation in W'
    )

    def diff(self, other: 'DVDataset') -> dict[str, tuple]:
        """Fields that changed between self and other as {field: (self_value, other_value)}.

        Useful for change-detection in polling loops — only act when something moved.
        """
        return {
            f: (getattr(self, f), getattr(other, f))
            for f in type(self).model_fields
            if getattr(self, f) != getattr(other, f)
        }


class DVReadResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    interface: str
    host: str | None
    elapsed_s: float = Field(ge=0)
    read_at: datetime = Field(
        default_factory=lambda: datetime.now(tz=timezone.utc),
        description='UTC timestamp when the read was initiated',
    )
    dataset: DVDataset

    @field_serializer('elapsed_s')
    def _round_elapsed(self, v: float) -> float:
        return round(v, 3)

    @property
    def age_s(self) -> float:
        """Seconds elapsed since this result was captured."""
        return (datetime.now(tz=timezone.utc) - self.read_at).total_seconds()

    def is_stale(self, max_age_s: float) -> bool:
        """True if this result is older than max_age_s seconds."""
        return self.age_s > max_age_s

    def to_dict(self) -> dict:
        """Flat dict for direct database insertion or task queue result serialization.

        read_at is serialized as an ISO 8601 string (UTC).
        """
        return {
            **self.model_dump(exclude={'dataset', 'read_at'}),
            **self.dataset.model_dump(),
            'read_at': self.read_at.isoformat(),
        }


class DVInterfaceBase(ABC):
    interface: ClassVar[str]
    supports_dv_percent_limit: ClassVar[bool] = True
    supports_dv_watt_limit: ClassVar[bool] = True

    def __init__(self, config: Any = None) -> None:
        if not hasattr(self, 'interface'):
            raise TypeError(
                f'{type(self).__name__} must define class attribute interface: str'
            )
        self.config = config

    def __repr__(self) -> str:
        return f'<{type(self).__name__} config={self.config}>'

    @abstractmethod
    def read_production(self) -> int:
        """Realtime production in W."""

    @abstractmethod
    def read_gridfeed(self) -> int:
        """Realtime grid feed in W. Feed (+), Use (-)."""

    @abstractmethod
    def read_consumption(self) -> int:
        """Realtime consumption in W."""

    @abstractmethod
    def read_limitation_nb_percent(self) -> float | None:
        """Netzbetreiber limitation in %."""

    @abstractmethod
    def read_limitation_nb_w(self) -> float | None:
        """Netzbetreiber limitation in W."""

    @abstractmethod
    def read_limitation_dv_percent(self) -> float | None:
        """Direktvermarkter limitation in %."""

    @abstractmethod
    def read_limitation_dv_w(self) -> float | None:
        """Direktvermarkter limitation in W."""

    @abstractmethod
    def set_limitation_dv_percent(self, percent: float) -> None:
        """Limit plant output to percent %."""

    @abstractmethod
    def set_limitation_dv_w(self, watts: float) -> None:
        """Limit plant output to watts W."""

    @abstractmethod
    def turn_on(self) -> None:
        """Set plant to maximum output (no limitation)."""

    @abstractmethod
    def turn_off(self) -> None:
        """Set plant to minimum output."""

    @abstractmethod
    def connect(self) -> None:
        """Open the connection to the device."""

    @abstractmethod
    def disconnect(self) -> None:
        """Close the connection to the device."""

    @property
    @abstractmethod
    def is_connected(self) -> bool:
        """True if the device connection is currently open."""

    def ping(self) -> bool:
        """Return True if a connection to the device can be established."""
        try:
            if not self.is_connected:
                self.connect()
            return self.is_connected
        except Exception:
            return False

    def __enter__(self) -> 'DVInterfaceBase':
        self.connect()
        return self

    def __exit__(self, exc_type: object, exc_val: object, exc_tb: object) -> bool:
        self.disconnect()
        return False

    def limit_plant(self, percent: float) -> None:
        """Convenience alias for set_limitation_dv_percent with range validation."""
        if not 0 <= percent <= 100:
            raise ValueError(f'percent must be between 0 and 100, got {percent}')
        self.set_limitation_dv_percent(percent)

    def read_dataset(self) -> DVDataset:
        """Read all metrics. Override in subclasses to batch the register reads."""
        return DVDataset(
            production=self.read_production(),
            consumption=self.read_consumption(),
            grid_feed=self.read_gridfeed(),
            limitation_nb_percent=self.read_limitation_nb_percent(),
            limitation_nb_w=self.read_limitation_nb_w(),
            limitation_dv_percent=self.read_limitation_dv_percent(),
            limitation_dv_w=self.read_limitation_dv_w(),
        )

    def read_dataset_result(self) -> DVReadResult:
        """Read all metrics and return a DVReadResult with timing metadata.

        Raises on any read failure — let the caller decide which exceptions to retry on.

        """
        read_at = datetime.now(tz=timezone.utc)
        start = time.monotonic()
        dataset = self.read_dataset()
        return DVReadResult(
            interface=self.interface,
            host=getattr(self, 'host', None),
            elapsed_s=time.monotonic() - start,
            read_at=read_at,
            dataset=dataset,
        )
