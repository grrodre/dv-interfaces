import logging
import time
from typing import ClassVar

from ..base_interface import DVDataset
from ..exceptions import (
    ErrorDVInterface,
    ErrorLimitingDVInterface,
    ErrorTurnOffDVInterface,
    ErrorTurnOnDVInterface,
    ErrorUnsupportedOperationDVInterface,
)
from ..modbus import DVInterfaceModbusBase

logger = logging.getLogger(__name__)


class Solarlog(DVInterfaceModbusBase):
    interface = 'solarlog'
    supports_dv_watt_limit = False
    _byteorder = '>'
    _wordorder = '<'
    _probe_slave_id: ClassVar[int] = 1

    @classmethod
    def _probe_connected(cls, client, slave_id: int) -> int:
        score = 0
        rq = client.read_input_registers(10900, count=1, device_id=slave_id)
        if not rq.isError():
            score += 1
        rq = client.read_input_registers(10904, count=2, device_id=slave_id)
        if not rq.isError():
            score += 1
        return score

    def read_production(self) -> int:
        return self._read_input_uint32(10904)

    def read_gridfeed(self) -> int:
        return self._read_input_int32(10910)

    def read_consumption(self) -> int:
        return self._read_input_uint32(10908)

    def status(self) -> int:
        return self._read_input_uint16(10900)

    def read_limitation_nb_percent(self) -> float | None:
        return float(self._read_input_uint16(10901))

    def read_limitation_nb_w(self) -> float | None:
        return (
            self._read_input_float32(10902) * 1000
        )  # register is in kW, DVDataset expects W

    def read_limitation_dv_percent(self) -> float | None:
        return None

    def read_limitation_dv_w(self) -> float | None:
        return None

    def set_limitation_dv_percent(self, percent: float) -> None:
        self._solarlog_write_control(mode=2, value=int(percent))

    def set_limitation_dv_w(self, watts: float) -> None:
        raise ErrorUnsupportedOperationDVInterface(
            'SolarLog does not support watt-based DV limiting'
        )

    def turn_on(self) -> None:
        self._solarlog_write_control(mode=1, value=100, exc_cls=ErrorTurnOnDVInterface)

    def turn_off(self) -> None:
        self._solarlog_write_control(mode=2, value=0, exc_cls=ErrorTurnOffDVInterface)

    def read_dataset(self) -> DVDataset:
        registers = self._read_input_registers(10900, 12)
        limitation_nb_percent = float(self._decode_uint16(registers[1:2]))
        limitation_nb_w = (
            self._decode_float32(registers[2:4]) * 1000
        )  # register is in kW, DVDataset expects W
        production = self._decode_uint32(registers[4:6])
        consumption = self._decode_uint32(registers[8:10])
        grid_feed = self._decode_int32(registers[10:12])
        return DVDataset(
            production=production,
            consumption=consumption,
            grid_feed=grid_feed,
            limitation_nb_percent=limitation_nb_percent,
            limitation_nb_w=limitation_nb_w,
            limitation_dv_percent=self.read_limitation_dv_percent(),
            limitation_dv_w=self.read_limitation_dv_w(),
        )

    # --- Extended reads ---

    def read_possible_production_w(self) -> int:
        """10906: Estimated possible plant power in W. Requires optional power sensor; returns 0 if no sensor."""
        return self._read_input_uint32(10906)

    def read_battery_charge_w(self) -> int:
        """10912: Current battery charging power in W. Requires battery driver, firmware >= 6.0.1."""
        return self._read_input_int32(10912)

    def read_battery_discharge_w(self) -> int:
        """10914: Current battery discharging power in W. Requires battery driver, firmware >= 6.0.1."""
        return self._read_input_int32(10914)

    # --- Private helpers ---

    def _solarlog_write_control(
        self,
        mode: int,
        value: int,
        exc_cls: type[ErrorDVInterface] = ErrorLimitingDVInterface,
    ) -> None:
        watchdog = int(time.time()) & 0xFFFFFFFF
        self._write_uint32(10404, watchdog, exc_cls)
        self._write_register(10400, mode, exc_cls)
        self._write_register(10401, value, exc_cls)
