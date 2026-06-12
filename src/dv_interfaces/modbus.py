import logging
import os
import time
from collections.abc import Callable, Mapping
from typing import Any, ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field
from pymodbus.client import ModbusTcpClient
from pymodbus.client.mixin import ModbusClientMixin
from pymodbus.exceptions import ModbusException

from .base_interface import DVInterfaceBase
from .exceptions import (
    ErrorConnectionDVInterface,
    ErrorDVInterface,
    ErrorLimitingDVInterface,
    ErrorReadDVInterface,
)

logger = logging.getLogger(__name__)

_DEFAULT_PORT = 502


class DVModbusConfiguration(BaseModel):
    """Validated protocol-level configuration for Modbus-based interfaces."""

    model_config = ConfigDict(frozen=True, extra='forbid')

    slave_id: int = Field(1, ge=1, le=247, description='Modbus slave ID (1–247)')
    timeout: float = Field(5.0, gt=0, description='TCP connection timeout in seconds')
    max_retries: int = Field(
        0, ge=0, description='Extra register-read attempts on failure'
    )
    retry_delay: float = Field(0.2, ge=0, description='Seconds between retry attempts')

    @classmethod
    def from_env(cls, prefix: str = 'DV') -> 'DVModbusConfiguration':
        """Build from environment variables.

        {prefix}_SLAVE_ID, {prefix}_TIMEOUT, {prefix}_MAX_RETRIES, {prefix}_RETRY_DELAY

        Example:
            DV_SLAVE_ID=2 DV_TIMEOUT=10 → DVModbusConfiguration(slave_id=2, timeout=10.0)
        """
        kwargs: dict = {}
        if v := os.environ.get(f'{prefix}_SLAVE_ID'):
            kwargs['slave_id'] = int(v)
        if v := os.environ.get(f'{prefix}_TIMEOUT'):
            kwargs['timeout'] = float(v)
        if v := os.environ.get(f'{prefix}_MAX_RETRIES'):
            kwargs['max_retries'] = int(v)
        if v := os.environ.get(f'{prefix}_RETRY_DELAY'):
            kwargs['retry_delay'] = float(v)
        return cls(**kwargs)


class DVInterfaceModbusBase(DVInterfaceBase):
    """Base class for Modbus TCP drivers.

    Drivers own their register maps. This base class provides connection
    lifecycle, retry handling, pymodbus-backed value conversion, and small typed
    read/write helpers for common scalar register values.
    """

    _byteorder: ClassVar[str]  # '>' big-endian or '<' little-endian
    _wordorder: ClassVar[str]  # '>' big-endian or '<' little-endian
    _probe_slave_id: ClassVar[int] = 1
    _default_slave_id: ClassVar[int] = 1

    @classmethod
    def _make_probe_client(
        cls, host: str, port: int, timeout: float
    ) -> ModbusTcpClient:
        return ModbusTcpClient(host, port=port, timeout=timeout)

    @classmethod
    def _probe(
        cls, host: str, port: int, timeout: float, *, slave_id: int | None = None
    ) -> int:
        """Return a driver-specific probe score for a reachable Modbus endpoint."""
        sid = slave_id if slave_id is not None else cls._probe_slave_id
        client = cls._make_probe_client(host, port, timeout)
        try:
            if not client.connect():
                return 0
            return cls._probe_connected(client, sid)
        except (ModbusException, OSError, TimeoutError):
            logger.debug(
                '%s: probe failed for %s:%s', cls.interface, host, port, exc_info=True
            )
            return 0
        finally:
            client.close()

    @classmethod
    def _probe_connected(cls, client: ModbusTcpClient, slave_id: int) -> int:
        """Probe driver-owned registers on an already-connected client."""
        return 0

    def __init__(
        self,
        host: str,
        port: int = _DEFAULT_PORT,
        modbus_config: DVModbusConfiguration | Mapping[str, Any] | None = None,
    ) -> None:
        config = self._resolve_modbus_config(modbus_config)
        super().__init__(config=config)
        self.host = host
        self.port = port
        self.modbus_config = config
        if self._byteorder != '>':
            raise ValueError('pymodbus register conversion expects big-endian bytes')
        self._client = ModbusTcpClient(
            host,
            port=port,
            timeout=self.modbus_config.timeout,
            retries=self.modbus_config.max_retries,
        )

    def __repr__(self) -> str:
        return f'<{type(self).__name__} {self.host}:{self.port} modbus_config={self.modbus_config}>'

    def _resolve_modbus_config(
        self,
        modbus_config: DVModbusConfiguration | Mapping[str, Any] | None,
    ) -> DVModbusConfiguration:
        if isinstance(modbus_config, DVModbusConfiguration):
            config = modbus_config
            if 'slave_id' not in config.model_fields_set:
                config = config.model_copy(update={'slave_id': self._default_slave_id})
        else:
            config_data = dict(modbus_config or {})
            if 'slave_id' not in config_data:
                config_data['slave_id'] = self._default_slave_id
            config = DVModbusConfiguration.model_validate(config_data)

        return config

    # --- Lifecycle ---

    @property
    def is_connected(self) -> bool:
        return self._client.is_socket_open()

    def connect(self) -> None:
        self._client.connect()

    def disconnect(self) -> None:
        self._client.close()

    # --- Internal helpers ---

    def _ensure_connected(self) -> None:
        """Reconnect if the socket was dropped between operations."""
        if not self.is_connected:
            logger.info(f'{self.interface}: reconnecting to {self.host}:{self.port}')
            try:
                self.connect()
            except Exception as exc:
                raise ErrorConnectionDVInterface(
                    f'{self.interface}: connection to {self.host}:{self.port} failed',
                    host=self.host,
                    port=self.port,
                ) from exc

    def _assert_response(
        self,
        rq: Any,
        exc_cls: type[ErrorDVInterface],
        operation: str,
    ) -> None:
        if rq.isError():
            logger.error(
                f'{self.interface}: {operation} failed. '
                f'Modbus config={self.modbus_config}. {rq}'
            )
            raise exc_cls(f'{self.interface}: {operation} failed')

    # --- Register read helpers ---

    @property
    def _pymodbus_word_order(self) -> Literal['big', 'little']:
        return 'little' if self._wordorder == '<' else 'big'

    def _read_register_block(
        self,
        read_fn: Callable[..., Any],
        operation_name: str,
        address: int,
        count: int,
        exc_cls: type[ErrorDVInterface] = ErrorReadDVInterface,
    ) -> list[int]:
        self._ensure_connected()
        op = f'{operation_name}({address}, {count})'
        rq: Any = None
        for attempt in range(self.modbus_config.max_retries + 1):
            rq = read_fn(address, count=count, device_id=self.modbus_config.slave_id)
            if not rq.isError():
                return list(rq.registers)
            if attempt < self.modbus_config.max_retries:
                logger.warning(
                    f'{self.interface}: {op} attempt {attempt + 1} failed, retrying'
                )
                time.sleep(self.modbus_config.retry_delay)
        logger.error(
            f'{self.interface}: {op} failed. Modbus config={self.modbus_config}. {rq}'
        )
        raise exc_cls(f'{self.interface}: {op} failed')

    def _read_input_registers(
        self,
        address: int,
        count: int,
        exc_cls: type[ErrorDVInterface] = ErrorReadDVInterface,
    ) -> list[int]:
        return self._read_register_block(
            self._client.read_input_registers,
            'read_input_registers',
            address,
            count,
            exc_cls,
        )

    def _read_holding_registers(
        self,
        address: int,
        count: int,
        exc_cls: type[ErrorDVInterface] = ErrorReadDVInterface,
    ) -> list[int]:
        return self._read_register_block(
            self._client.read_holding_registers,
            'read_holding_registers',
            address,
            count,
            exc_cls,
        )

    # --- Register write helpers ---

    def _write_register(
        self,
        address: int,
        value: int,
        exc_cls: type[ErrorDVInterface] = ErrorLimitingDVInterface,
    ) -> None:
        self._ensure_connected()
        rq = self._client.write_register(
            address, value, device_id=self.modbus_config.slave_id
        )
        self._assert_response(rq, exc_cls, f'write_register({address})')

    def _write_registers(
        self,
        address: int,
        values: list[int],
        exc_cls: type[ErrorDVInterface] = ErrorLimitingDVInterface,
    ) -> None:
        self._ensure_connected()
        rq = self._client.write_registers(
            address, values, device_id=self.modbus_config.slave_id
        )
        self._assert_response(rq, exc_cls, f'write_registers({address})')

    def _write_converted_registers(
        self,
        address: int,
        value: int | float,
        data_type: ModbusClientMixin.DATATYPE,
        exc_cls: type[ErrorDVInterface] = ErrorLimitingDVInterface,
    ) -> None:
        registers = ModbusTcpClient.convert_to_registers(
            value, data_type, word_order=self._pymodbus_word_order
        )
        self._write_registers(address, registers, exc_cls)

    # --- Payload conversion helpers ---

    def _decode_registers(
        self,
        registers: list[int],
        data_type: ModbusClientMixin.DATATYPE,
    ) -> int | float:
        value = ModbusTcpClient.convert_from_registers(
            registers,
            data_type,
            word_order=self._pymodbus_word_order,
        )
        if isinstance(value, list | str):
            raise TypeError(f'Expected scalar Modbus value, got {type(value).__name__}')
        return value

    # --- Typed read shortcuts ---

    def _decode_uint16(self, registers: list[int]) -> int:
        return int(self._decode_registers(registers, ModbusTcpClient.DATATYPE.UINT16))

    def _decode_uint32(self, registers: list[int]) -> int:
        return int(self._decode_registers(registers, ModbusTcpClient.DATATYPE.UINT32))

    def _decode_int32(self, registers: list[int]) -> int:
        return int(self._decode_registers(registers, ModbusTcpClient.DATATYPE.INT32))

    def _decode_float32(self, registers: list[int]) -> float:
        return float(
            self._decode_registers(registers, ModbusTcpClient.DATATYPE.FLOAT32)
        )

    def _decode_uint64(self, registers: list[int]) -> int:
        return int(self._decode_registers(registers, ModbusTcpClient.DATATYPE.UINT64))

    def _read_input_uint16(self, address: int) -> int:
        return self._decode_uint16(self._read_input_registers(address, 1))

    def _read_input_uint32(self, address: int) -> int:
        return self._decode_uint32(self._read_input_registers(address, 2))

    def _read_input_int32(self, address: int) -> int:
        return self._decode_int32(self._read_input_registers(address, 2))

    def _read_input_float32(self, address: int) -> float:
        return self._decode_float32(self._read_input_registers(address, 2))

    def _read_input_uint64(self, address: int) -> int:
        return self._decode_uint64(self._read_input_registers(address, 4))

    def _read_holding_int32(self, address: int) -> int:
        return self._decode_int32(self._read_holding_registers(address, 2))

    def _read_holding_float32(self, address: int) -> float:
        return self._decode_float32(self._read_holding_registers(address, 2))

    # --- Typed write shortcuts ---

    def _write_uint32(
        self,
        address: int,
        value: int,
        exc_cls: type[ErrorDVInterface] = ErrorLimitingDVInterface,
    ) -> None:
        self._write_converted_registers(
            address, value, ModbusTcpClient.DATATYPE.UINT32, exc_cls
        )

    def _write_int32(
        self,
        address: int,
        value: int,
        exc_cls: type[ErrorDVInterface] = ErrorLimitingDVInterface,
    ) -> None:
        self._write_converted_registers(
            address, value, ModbusTcpClient.DATATYPE.INT32, exc_cls
        )

    def _write_float32(
        self,
        address: int,
        value: float,
        exc_cls: type[ErrorDVInterface] = ErrorLimitingDVInterface,
    ) -> None:
        self._write_converted_registers(
            address, value, ModbusTcpClient.DATATYPE.FLOAT32, exc_cls
        )
