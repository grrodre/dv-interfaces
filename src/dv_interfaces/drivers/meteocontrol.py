import logging
import math
from typing import ClassVar

from ..exceptions import (
    ErrorDVInterface,
    ErrorLimitingDVInterface,
    ErrorTurnOffDVInterface,
    ErrorTurnOnDVInterface,
)
from ..modbus import DVInterfaceModbusBase

logger = logging.getLogger(__name__)

# Meteocontrol blue'Log XC — Remote Power Control (RPC) Modbus TCP
# Spec: Remote-Power-Control_de_2025-11-14_meteocontrol.pdf (Version 1.42)
_MC_SLAVE_ID = 10  # fixed slave address per RPC specification


class Meteocontrol(DVInterfaceModbusBase):
    interface = 'meteocontrol'
    _byteorder = '>'  # HIGH byte before LOW byte (Big Endian)
    _wordorder = '<'  # LOW register before HIGH register (Little Endian)
    _probe_slave_id: ClassVar[int] = _MC_SLAVE_ID
    _default_slave_id: ClassVar[int] = _MC_SLAVE_ID

    @classmethod
    def _probe_connected(cls, client, slave_id: int) -> int:
        score = 0
        rq = client.read_holding_registers(0, count=2, device_id=slave_id)
        if not rq.isError():
            score += 1
        rq = client.read_holding_registers(2, count=2, device_id=slave_id)
        if not rq.isError():
            score += 1
        return score

    # ── DVInterfaceBase abstract methods ──────────────────────────────────────

    def read_production(self) -> int:
        # 0: PPC_P_AC_INV — Wechselrichterwirkleistung [W, F32]
        return int(self._mc_read_f32(0))

    def read_gridfeed(self) -> int:
        # 2: PPC_P_AC_FEED_IN — Einspeiseleistung am Netzanschlusspunkt [W, F32]
        # Positive = export (Erzeugung), negative = import (Bezug)
        return int(self._mc_read_f32(2))

    def read_consumption(self) -> int:
        return self.read_production() - self.read_gridfeed()

    def read_limitation_nb_percent(self) -> float | None:
        # 6: PPC_P_SET_GRIDOP_REL — Wirkleistungssollwert Netzbetreiber [%, F32]
        raw = self._mc_read_f32(6)
        return None if math.isnan(raw) else raw

    def read_limitation_nb_w(self) -> float | None:
        # 10: PPC_P_AC_GRIDOP_MAX — Maximale Wirkleistung bei NB-Begrenzung [W, F32]
        raw = self._mc_read_f32(10)
        return None if math.isnan(raw) else raw

    def read_limitation_dv_percent(self) -> float | None:
        # 8: PPC_P_SET_RPC_REL — Wirkleistungs-Sollwert Direktvermarkter [%, F32]
        raw = self._mc_read_f32(8)
        return None if math.isnan(raw) else raw

    def read_limitation_dv_w(self) -> float | None:
        # 44: PPC_P_SET_RPC_ABS — Absoluter Wirkleistungssollwert Dritte [W, F32]
        raw = self._mc_read_f32(44)
        return None if math.isnan(raw) else raw

    def set_limitation_dv_percent(self, percent: float) -> None:
        # 5000: PPC_P_SET_RPC_REL — relative DV setpoint [%, F32, W]
        self._mc_write_f32(5000, percent, ErrorLimitingDVInterface)

    def set_limitation_dv_w(self, watts: float) -> None:
        # 5002: PPC_P_SET_RPC_ABS — absolute DV setpoint [W, F32, W]
        self._mc_write_f32(5002, watts, ErrorLimitingDVInterface)

    def turn_on(self) -> None:
        # 5000 = 100.0 % → full power
        self._mc_write_f32(5000, 100.0, ErrorTurnOnDVInterface)

    def turn_off(self) -> None:
        # 5000 = 0.0 % → no output
        self._mc_write_f32(5000, 0.0, ErrorTurnOffDVInterface)

    # ── Power & grid ──────────────────────────────────────────────────────────

    def read_effective_limit_percent(self) -> float | None:
        """4: PPC_P_SET_REL — Resulting setpoint (minimum of all sources) [%, F32]."""
        raw = self._mc_read_f32(4)
        return None if math.isnan(raw) else raw

    def read_dv_limit_w(self) -> float | None:
        """12: PPC_P_AC_RPC_MAX — Max power at DV curtailment [W, F32]."""
        raw = self._mc_read_f32(12)
        return None if math.isnan(raw) else raw

    def read_available_power_w(self) -> float | None:
        """24: PPC_P_AC_AVAIL — Currently available active power [W, F32]."""
        raw = self._mc_read_f32(24)
        return None if math.isnan(raw) else raw

    def read_available_reactive_power_var(self) -> float | None:
        """26: PPC_Q_AC_AVAIL — Currently available reactive power [Var, F32]."""
        raw = self._mc_read_f32(26)
        return None if math.isnan(raw) else raw

    def read_grid_frequency_hz(self) -> float | None:
        """42: PPC_F_AC — Grid frequency [Hz, F32]."""
        raw = self._mc_read_f32(42)
        return None if math.isnan(raw) else raw

    def read_agreed_connection_power_w(self) -> float | None:
        """4000: PPC_P_AV_E — Agreed connection active power PAV [W, F32]."""
        raw = self._mc_read_f32(4000)
        return None if math.isnan(raw) else raw

    # ── Environmental sensors ─────────────────────────────────────────────────

    def read_irradiance_w_m2(self) -> float | None:
        """20: PPC_GHI — Global horizontal irradiance [W/m², F32]."""
        raw = self._mc_read_f32(20)
        return None if math.isnan(raw) else raw

    def read_ambient_temperature_c(self) -> float | None:
        """22: PPC_T_AMBIENT — Ambient temperature [°C, F32]."""
        raw = self._mc_read_f32(22)
        return None if math.isnan(raw) else raw

    # ── Battery ───────────────────────────────────────────────────────────────

    def read_battery_soc_percent(self) -> float | None:
        """32: PPC_BAT_SOC — Battery state of charge [%, F32]. None if no battery."""
        raw = self._mc_read_f32(32)
        return None if math.isnan(raw) else raw

    def read_battery_soc_wh(self) -> float | None:
        """34: PPC_BAT_SOC_ABS — Battery state of charge absolute [Wh, F32]."""
        raw = self._mc_read_f32(34)
        return None if math.isnan(raw) else raw

    def read_battery_capacity_wh(self) -> float | None:
        """36: PPC_BAT_CAP — Battery capacity [Wh, F32]."""
        raw = self._mc_read_f32(36)
        return None if math.isnan(raw) else raw

    def read_battery_power_w(self) -> float | None:
        """38: PPC_BAT_P_AC_INV — Sum of battery inverter power [W, F32]."""
        raw = self._mc_read_f32(38)
        return None if math.isnan(raw) else raw

    def read_pv_power_w(self) -> float | None:
        """40: PPC_PV_P_AC_INV — Sum of PV inverter power [W, F32]."""
        raw = self._mc_read_f32(40)
        return None if math.isnan(raw) else raw

    # ── Private helpers ───────────────────────────────────────────────────────

    def _mc_read_f32(self, address: int) -> float:
        return self._read_holding_float32(address)

    def _mc_write_f32(
        self,
        address: int,
        value: float,
        exc_cls: type[ErrorDVInterface] = ErrorLimitingDVInterface,
    ) -> None:
        self._write_float32(address, value, exc_cls)
