import logging
from typing import ClassVar

from ..exceptions import (
    ErrorDVInterface,
    ErrorLimitingDVInterface,
    ErrorTurnOffDVInterface,
    ErrorTurnOnDVInterface,
)
from ..modbus import DVInterfaceModbusBase

logger = logging.getLogger(__name__)

# ecodata PowerDog / SmartDog — Modbus Register Specification (12.10.2023, min fw 1.96-r2986)
# All registers: Signed 32-bit, Big Endian, Holding Registers (FC03/FC16)
# SmartDog documents values in Verbraucherpfeilsystem (consumer reference direction):
#   positive = Bezug/import, negative = Liefern/export.
# Exception: register 40090 uses Erzeugerpfeilsystem (generator reference direction)
# NaN sentinel: -1 ("Nicht erfasst" = not captured)
# IMPORTANT: Setpoint registers 40004 and 40014 have a 5-minute timeout.
#   They reset unless Modbus communication (read OR write) occurs within 5 minutes.
_ECODATA_DV_UNIT_ID = 2  # Direktvermarkter slave ID (configurable, default 2)
_NOT_CAPTURED = -1


class Smartdog(DVInterfaceModbusBase):
    interface = 'smartdog'
    _byteorder = '>'
    _wordorder = '>'
    _probe_slave_id: ClassVar[int] = _ECODATA_DV_UNIT_ID
    _default_slave_id: ClassVar[int] = _ECODATA_DV_UNIT_ID

    @classmethod
    def _probe_connected(cls, client, slave_id: int) -> int:
        score = 0
        rq = client.read_holding_registers(40000, count=2, device_id=slave_id)
        if not rq.isError():
            score += 1
        rq = client.read_holding_registers(40002, count=2, device_id=slave_id)
        if not rq.isError():
            score += 1
        return score

    # ── DVInterfaceBase abstract methods ──────────────────────────────────────

    def read_production(self) -> int:
        # 40002: Aktuelle erzeugte Leistung [W, S32]
        return self._ecodata_read_s32(40002)

    def read_gridfeed(self) -> int:
        # 40000: Aktuelle Leistung Einspeisepunkt [W, S32] — Verbraucherpfeilsystem
        # Negate for the public contract: positive grid_feed means export/feed-in.
        return -self._ecodata_read_s32(40000)

    def read_consumption(self) -> int:
        # 40026: Gesamtverbrauch [W, S32]
        return self._ecodata_read_s32(40026)

    def read_limitation_nb_percent(self) -> float | None:
        # No percentage register available; caller can derive from nb_w / rated_power
        return None

    def read_limitation_nb_w(self) -> float | None:
        # 40006: Maximal zulässige Leistung vom Energieversorger [W, S32]
        raw = self._ecodata_read_s32(40006)
        return None if raw == _NOT_CAPTURED else float(raw)

    def read_limitation_dv_percent(self) -> float | None:
        # No percentage register available; caller can derive from dv_w / rated_power
        return None

    def read_limitation_dv_w(self) -> float | None:
        # 40004: Maximal zulässige Leistung vom Direktvermarkter [W, S32]
        raw = self._ecodata_read_s32(40004)
        return None if raw == _NOT_CAPTURED else float(raw)

    def set_limitation_dv_percent(self, percent: float) -> None:
        # Derive watts from rated plant power (40012: Nennleistung [VA, S32])
        rated = self._ecodata_read_s32(40012)
        if rated <= 0 or rated == _NOT_CAPTURED:
            raise ErrorLimitingDVInterface(
                f'{self.interface}: rated power not available, cannot set percent limit'
            )
        self._ecodata_set_dv_limit(int(rated * percent / 100), ErrorLimitingDVInterface)

    def set_limitation_dv_w(self, watts: float) -> None:
        self._ecodata_set_dv_limit(int(watts), ErrorLimitingDVInterface)

    def turn_on(self) -> None:
        # Deactivate DV limitation (0 = Deaktiviert) — PV runs freely subject to EVU limits
        self._ecodata_write_s32(40014, 0, ErrorTurnOnDVInterface)

    def turn_off(self) -> None:
        # Set 0 W limit and activate (1 = Aktiviert)
        self._ecodata_set_dv_limit(0, ErrorTurnOffDVInterface)

    # ── Power & grid ──────────────────────────────────────────────────────────

    def read_available_power_w(self) -> int | None:
        """40020: Aktuell verfügbare Wirkleistung [W, S32]."""
        raw = self._ecodata_read_s32(40020)
        return None if raw == _NOT_CAPTURED else raw

    def read_grid_draw_w(self) -> int | None:
        """40024: Netzbezug — current grid import [W, S32]."""
        raw = self._ecodata_read_s32(40024)
        return None if raw == _NOT_CAPTURED else raw

    def read_self_consumption_w(self) -> int | None:
        """40028: Eigenverbrauch — self-consumption from PV [W, S32]."""
        raw = self._ecodata_read_s32(40028)
        return None if raw == _NOT_CAPTURED else raw

    def read_rated_power_va(self) -> int | None:
        """40012: Nennleistung der Anlage [VA, S32]."""
        raw = self._ecodata_read_s32(40012)
        return None if raw == _NOT_CAPTURED else raw

    def read_reactive_power_plant_var(self) -> int | None:
        """40048: Blindleistung der Erzeugungsanlage [VAr, S32]. None if not captured."""
        raw = self._ecodata_read_s32(40048)
        return None if raw == _NOT_CAPTURED else raw

    def read_reactive_power_grid_var(self) -> int | None:
        """40050: Blindleistung am Einspeisepunkt [VAr, S32]. None if not captured."""
        raw = self._ecodata_read_s32(40050)
        return None if raw == _NOT_CAPTURED else raw

    # ── Battery ───────────────────────────────────────────────────────────────

    def read_battery_power_w(self) -> int | None:
        """40036: Batterieladung [W, S32]. Negative = charging, positive = discharging."""
        raw = self._ecodata_read_s32(40036)
        return None if raw == _NOT_CAPTURED else raw

    def read_battery_soc_percent(self) -> int | None:
        """40038: Batterieladezustand [%, S32]."""
        raw = self._ecodata_read_s32(40038)
        return None if raw == _NOT_CAPTURED else raw

    # ── Environmental sensors ─────────────────────────────────────────────────

    def read_irradiance_w_m2(self) -> int | None:
        """40040: Sonneneinstrahlung [W/m², S32]. None if no sensor."""
        raw = self._ecodata_read_s32(40040)
        return None if raw == _NOT_CAPTURED else raw

    def read_module_temperature_c(self) -> int | None:
        """40044: Modultemperatur [°C, S32]. None if no sensor."""
        raw = self._ecodata_read_s32(40044)
        return None if raw == _NOT_CAPTURED else raw

    def read_ambient_temperature_c(self) -> int | None:
        """40046: Aussentemperatur [°C, S32]. None if no sensor."""
        raw = self._ecodata_read_s32(40046)
        return None if raw == _NOT_CAPTURED else raw

    # ── Phase measurements (Carlo Gavazzi EM24 meter only) ────────────────────

    def read_phase_voltages_v(self) -> tuple[int | None, int | None, int | None]:
        """40062–40066: Phase-to-neutral voltages U1N, U2N, U3N [V, S32]. Carlo Gavazzi EM24 only."""
        u1 = self._ecodata_read_s32(40062)
        u2 = self._ecodata_read_s32(40064)
        u3 = self._ecodata_read_s32(40066)
        return (
            None if u1 == _NOT_CAPTURED else u1,
            None if u2 == _NOT_CAPTURED else u2,
            None if u3 == _NOT_CAPTURED else u3,
        )

    def read_phase_currents_a(self) -> tuple[int | None, int | None, int | None]:
        """40074–40078: Phase currents L1, L2, L3 [A, S32]. Carlo Gavazzi EM24 only."""
        l1 = self._ecodata_read_s32(40074)
        l2 = self._ecodata_read_s32(40076)
        l3 = self._ecodata_read_s32(40078)
        return (
            None if l1 == _NOT_CAPTURED else l1,
            None if l2 == _NOT_CAPTURED else l2,
            None if l3 == _NOT_CAPTURED else l3,
        )

    def read_grid_frequency_hz(self) -> int | None:
        """40080: Frequenz am Einspeisepunkt [Hz, S32]. Carlo Gavazzi EM24 only."""
        raw = self._ecodata_read_s32(40080)
        return None if raw == _NOT_CAPTURED else raw

    # ── Private helpers ───────────────────────────────────────────────────────

    def _ecodata_set_dv_limit(
        self, watts: int, exc_cls: type[ErrorDVInterface]
    ) -> None:
        """Write power limit and activate DV control in one operation."""
        self._ecodata_write_s32(40004, watts, exc_cls)
        self._ecodata_write_s32(40014, 1, exc_cls)

    def _ecodata_read_s32(self, address: int) -> int:
        return self._read_holding_int32(address)

    def _ecodata_write_s32(
        self,
        address: int,
        value: int,
        exc_cls: type[ErrorDVInterface] = ErrorLimitingDVInterface,
    ) -> None:
        self._write_int32(address, value, exc_cls)
