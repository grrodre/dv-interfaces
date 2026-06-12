import logging
from typing import ClassVar

from ..exceptions import (
    ErrorDVInterface,
    ErrorLimitingDVInterface,
    ErrorTurnOffDVInterface,
    ErrorTurnOnDVInterface,
    ErrorUnsupportedOperationDVInterface,
)
from ..modbus import DVInterfaceModbusBase

logger = logging.getLogger(__name__)

# All plant measurement and control registers live under Unit ID = 2 (Anlage).
# Unit ID = 1 is reserved for device info (serial number, firmware version, etc.).
_SMA_UNIT_ID = 2

# SMA NaN sentinels (see EDMx-Modbus-TI-de-16, section 3.4.5)
_NAN_U32 = 0xFFFF_FFFF
_NAN_S32 = -2_147_483_648  # 0x8000_0000 interpreted as int32
_NAN_U64 = 0xFFFF_FFFF_FFFF_FFFF

# Inverter quick-control codes for register 40018
_CTRL_STANDBY = 311
_CTRL_START = 1467
_CTRL_FULL_STOP = 1749


class Sma(DVInterfaceModbusBase):
    interface = 'sma'
    supports_dv_watt_limit = False
    _byteorder = '>'
    _wordorder = '>'
    _probe_slave_id: ClassVar[int] = _SMA_UNIT_ID
    _default_slave_id: ClassVar[int] = _SMA_UNIT_ID

    @classmethod
    def _probe_connected(cls, client, slave_id: int) -> int:
        score = 0
        rq = client.read_input_registers(30201, count=2, device_id=slave_id)
        if not rq.isError():
            score += 1
        rq = client.read_input_registers(30775, count=2, device_id=slave_id)
        if not rq.isError():
            score += 1
        return score

    # ── DVInterfaceBase abstract methods ──────────────────────────────────────

    def read_production(self) -> int:
        # 30775: Aktuelle PV-Einspeisewirkleistung über alle Außenleiter, in W (S32, FIX0)
        return self._sma_read_s32(30775)

    def read_gridfeed(self) -> int:
        # 31249: Anlagen-Wirkleistung am PCC, in W (S32, FIX0) — positive=feed, negative=draw
        return self._sma_read_s32(31249)

    def read_consumption(self) -> int:
        return self.read_production() - self.read_gridfeed()

    def read_limitation_nb_percent(self) -> float | None:
        # 31239: PV-Leistungsbegrenzung über Kommunikation, in % (U32, FIX2)
        raw = self._sma_read_u32(31239)
        return None if raw == _NAN_U32 else raw / 100

    def read_limitation_nb_w(self) -> float | None:
        return None

    def read_limitation_dv_percent(self) -> float | None:
        # 31241: PV-Leistungsbegrenzung über Kommunikation für Direktvermarktung, in % (U32, FIX2)
        raw = self._sma_read_u32(31241)
        return None if raw == _NAN_U32 else raw / 100

    def read_limitation_dv_w(self) -> float | None:
        return None

    def set_limitation_dv_percent(self, percent: float) -> None:
        # 40493: Direktvermarkter setpoint in % of PMAX (S16, FIX2, RW)
        self._sma_write_s16(40493, int(percent * 100), ErrorLimitingDVInterface)

    def set_limitation_dv_w(self, watts: float) -> None:
        raise ErrorUnsupportedOperationDVInterface(
            'SMA does not support watt-based DV limiting'
        )

    def turn_off(self) -> None:
        # 40493 = 0 → 0.00 % = keine Wirkleistung
        self._sma_write_s16(40493, 0, ErrorTurnOffDVInterface)

    def turn_on(self) -> None:
        # 40493 = 10000 → 100.00 % = full power (FIX2)
        self._sma_write_s16(40493, 10000, ErrorTurnOnDVInterface)

    # ── Power & grid ──────────────────────────────────────────────────────────

    def read_reactive_power_var(self) -> int | None:
        """30805: Reactive power across all conductors, in var (S32, FIX0)."""
        raw = self._sma_read_s32(30805)
        return None if raw == _NAN_S32 else raw

    def read_displacement_factor(self) -> float | None:
        """31525: Displacement factor (cos phi) at PCC (S32, FIX2)."""
        raw = self._sma_read_s32(31525)
        return None if raw == _NAN_S32 else raw / 100

    def read_grid_frequency_hz(self) -> float | None:
        """31527: Grid frequency at PCC, in Hz (U32, FIX2)."""
        raw = self._sma_read_u32(31527)
        return None if raw == _NAN_U32 else raw / 100

    def read_available_power_w(self) -> int | None:
        """31547: Available active power of all inverters, in W (U32, FIX0)."""
        raw = self._sma_read_u32(31547)
        return None if raw == _NAN_U32 else raw

    def read_max_available_power_w(self) -> int | None:
        """31545: Power value when all generation units are operating, in W (U32, FIX0)."""
        raw = self._sma_read_u32(31545)
        return None if raw == _NAN_U32 else raw

    # ── Phase measurements ────────────────────────────────────────────────────

    def read_phase_feed_w(self) -> tuple[int | None, int | None, int | None]:
        """31503–31507: Grid feed per phase at PCC, in W (S32, FIX0). Returns (L1, L2, L3)."""
        l1 = self._sma_read_s32(31503)
        l2 = self._sma_read_s32(31505)
        l3 = self._sma_read_s32(31507)
        return (
            None if l1 == _NAN_S32 else l1,
            None if l2 == _NAN_S32 else l2,
            None if l3 == _NAN_S32 else l3,
        )

    def read_phase_voltages_v(self) -> tuple[float | None, float | None, float | None]:
        """31529–31533: Phase voltages L1, L2, L3 at PCC, in V (U32, FIX2). Returns (L1, L2, L3)."""
        l1 = self._sma_read_u32(31529)
        l2 = self._sma_read_u32(31531)
        l3 = self._sma_read_u32(31533)
        return (
            None if l1 == _NAN_U32 else l1 / 100,
            None if l2 == _NAN_U32 else l2 / 100,
            None if l3 == _NAN_U32 else l3 / 100,
        )

    # ── Power limitation reads ────────────────────────────────────────────────

    def read_limitation_digital_input_percent(self) -> float | None:
        """31235: Active power limitation via digital input, in % (U32, FIX2)."""
        raw = self._sma_read_u32(31235)
        return None if raw == _NAN_U32 else raw / 100

    def read_limitation_analog_input_percent(self) -> float | None:
        """31237: Active power limitation setpoint via analog input, in % (U32, FIX2)."""
        raw = self._sma_read_u32(31237)
        return None if raw == _NAN_U32 else raw / 100

    def read_limitation_max_percent(self) -> float | None:
        """31243: Maximum active power setpoint, in % (U32, FIX2)."""
        raw = self._sma_read_u32(31243)
        return None if raw == _NAN_U32 else raw / 100

    def read_limitation_internal_percent(self) -> float | None:
        """31245: Internal PV power limitation, in % (U32, FIX2)."""
        raw = self._sma_read_u32(31245)
        return None if raw == _NAN_U32 else raw / 100

    def read_external_power_reduction_percent(self) -> float | None:
        """32195: External active power reduction, in % (U32, FIX2). None if disabled."""
        raw = self._sma_read_u32(32195)
        return None if raw == _NAN_U32 else raw / 100

    def set_manual_power_limit_percent(self, percent: float) -> None:
        """41167: Manually configured active power limit for the plant, in % (U32, FIX2, RW)."""
        self._sma_write_u32(41167, int(percent * 100), ErrorLimitingDVInterface)

    # ── Energy counters ───────────────────────────────────────────────────────

    def read_energy_total_wh(self) -> int | None:
        """30513: Total energy fed in across all conductors, in Wh (U64, FIX0)."""
        raw = self._sma_read_u64(30513)
        return None if raw == _NAN_U64 else raw

    def read_energy_today_wh(self) -> int | None:
        """30517: Energy fed in on the current day, in Wh (U64, FIX0)."""
        raw = self._sma_read_u64(30517)
        return None if raw == _NAN_U64 else raw

    # ── Battery ───────────────────────────────────────────────────────────────

    def read_battery_soc_percent(self) -> float | None:
        """30845: Battery state of charge, in % (U32, FIX0). None if no battery installed."""
        raw = self._sma_read_u32(30845)
        return None if raw == _NAN_U32 else float(raw)

    def read_battery_charge_w(self) -> int | None:
        """31393: Instantaneous battery charge power, in W (U32, FIX0). None if no battery."""
        raw = self._sma_read_u32(31393)
        return None if raw == _NAN_U32 else raw

    def read_battery_discharge_w(self) -> int | None:
        """31395: Instantaneous battery discharge power, in W (U32, FIX0). None if no battery."""
        raw = self._sma_read_u32(31395)
        return None if raw == _NAN_U32 else raw

    def read_battery_charge_total_wh(self) -> int | None:
        """31397: Total battery charge energy, in Wh (U64, FIX0). None if no battery."""
        raw = self._sma_read_u64(31397)
        return None if raw == _NAN_U64 else raw

    def read_battery_discharge_total_wh(self) -> int | None:
        """31401: Total battery discharge energy, in Wh (U64, FIX0). None if no battery."""
        raw = self._sma_read_u64(31401)
        return None if raw == _NAN_U64 else raw

    # ── Plant status ──────────────────────────────────────────────────────────

    def read_health_status(self) -> int | None:
        """30201: Health status 5-minute value (U32, ENUM). See SMA code table in EDMx doc."""
        raw = self._sma_read_u32(30201)
        return None if raw == _NAN_U32 else raw

    def read_plant_availability_percent(self) -> float | None:
        """32193: Plant availability, in % (U32, FIX0)."""
        raw = self._sma_read_u32(32193)
        return None if raw == _NAN_U32 else float(raw)

    # ── Environmental sensors (require sensors installed and configured) ───────

    def read_ambient_temperature_c(self) -> float | None:
        """34609: Ambient temperature in °C (S32, TEMP/FIX1). None if no sensor."""
        raw = self._sma_read_s32(34609)
        return None if raw == _NAN_S32 else raw / 10

    def read_module_temperature_c(self) -> float | None:
        """34621: PV module temperature in °C (S32, TEMP/FIX1). None if no sensor."""
        raw = self._sma_read_s32(34621)
        return None if raw == _NAN_S32 else raw / 10

    def read_irradiance_w_m2(self) -> int | None:
        """34623: Global irradiance on pyranometer, in W/m² (U32, FIX0). None if no sensor."""
        raw = self._sma_read_u32(34623)
        return None if raw == _NAN_U32 else raw

    def read_wind_speed_ms(self) -> float | None:
        """34615: Global wind speed, in m/s (U32, FIX2). None if no sensor."""
        raw = self._sma_read_u32(34615)
        return None if raw == _NAN_U32 else raw / 100

    # ── Inverter hardware control (register 40018) ────────────────────────────

    def inverter_stop(self) -> None:
        """40018=1749: Full stop — shuts down AC and DC side."""
        self._sma_write_u32(40018, _CTRL_FULL_STOP, ErrorTurnOffDVInterface)

    def inverter_start(self) -> None:
        """40018=1467: Start inverter."""
        self._sma_write_u32(40018, _CTRL_START, ErrorTurnOnDVInterface)

    def inverter_standby(self) -> None:
        """40018=311: Set inverter to standby."""
        self._sma_write_u32(40018, _CTRL_STANDBY, ErrorLimitingDVInterface)

    # ── Private helpers ───────────────────────────────────────────────────────

    def _sma_read_u32(self, address: int) -> int:
        return self._read_input_uint32(address)

    def _sma_read_s32(self, address: int) -> int:
        return self._read_input_int32(address)

    def _sma_read_u64(self, address: int) -> int:
        return self._read_input_uint64(address)

    def _sma_write_s16(
        self,
        address: int,
        value: int,
        exc_cls: type[ErrorDVInterface] = ErrorLimitingDVInterface,
    ) -> None:
        self._ensure_connected()
        rq = self._client.write_register(
            address, value=value, device_id=self.modbus_config.slave_id
        )
        self._assert_response(rq, exc_cls, f'write_register({address})')

    def _sma_write_u32(
        self,
        address: int,
        value: int,
        exc_cls: type[ErrorDVInterface] = ErrorLimitingDVInterface,
    ) -> None:
        self._write_uint32(address, value, exc_cls)
