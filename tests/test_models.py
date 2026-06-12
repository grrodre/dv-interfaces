"""Tests for DVDataset and DVReadResult validation."""

import time

import pytest
from pydantic import ValidationError

from dv_interfaces.base_interface import DVDataset, DVReadResult


def _dataset(**kwargs):
    defaults = dict(production=1000, consumption=800, grid_feed=200)
    return DVDataset(**{**defaults, **kwargs})


class TestDVDataset:
    def test_minimal_valid(self):
        d = _dataset()
        assert d.production == 1000
        assert d.limitation_nb_percent is None

    def test_grid_feed_can_be_negative(self):
        d = _dataset(grid_feed=-500)
        assert d.grid_feed == -500

    def test_percent_zero_allowed(self):
        d = _dataset(limitation_nb_percent=0.0, limitation_dv_percent=0.0)
        assert d.limitation_nb_percent == 0.0

    def test_percent_100_allowed(self):
        d = _dataset(limitation_nb_percent=100.0, limitation_dv_percent=100.0)
        assert d.limitation_nb_percent == 100.0

    def test_percent_125_allowed(self):
        # Meteocontrol allows values above 100
        d = _dataset(limitation_nb_percent=125.0, limitation_dv_percent=125.0)
        assert d.limitation_nb_percent == 125.0

    def test_limitation_dv_percent_negative_allowed(self):
        d = _dataset(limitation_dv_percent=-1.0)
        assert d.limitation_dv_percent == -1.0

    def test_limitation_dv_percent_above_125_allowed(self):
        d = _dataset(limitation_dv_percent=130.0)
        assert d.limitation_dv_percent == 130.0

    def test_limitation_w_non_negative(self):
        d = _dataset(limitation_nb_w=5000.0, limitation_dv_w=3000.0)
        assert d.limitation_nb_w == 5000.0

    def test_frozen(self):
        d = _dataset()
        with pytest.raises(ValidationError):
            d.production = 999  # type: ignore[misc]

    def test_diff_empty_when_equal(self):
        d = _dataset()
        assert d.diff(d) == {}

    def test_diff_detects_changed_fields(self):
        a = _dataset(production=1000, consumption=800)
        b = _dataset(production=2000, consumption=800)
        changed = a.diff(b)
        assert set(changed.keys()) == {'production'}
        assert changed['production'] == (1000, 2000)

    def test_diff_detects_none_to_value(self):
        a = _dataset(limitation_dv_percent=None)
        b = _dataset(limitation_dv_percent=70.0)
        changed = a.diff(b)
        assert 'limitation_dv_percent' in changed
        assert changed['limitation_dv_percent'] == (None, 70.0)

    def test_diff_multiple_fields(self):
        a = _dataset(production=1000, grid_feed=200)
        b = _dataset(production=1500, grid_feed=-100)
        changed = a.diff(b)
        assert set(changed.keys()) == {'production', 'grid_feed'}


class TestDVReadResult:
    def _result(
        self,
        interface: str = 'solarlog',
        host: str | None = '192.168.1.1',
        elapsed_s: float = 0.5,
        dataset: DVDataset | None = None,
    ) -> DVReadResult:
        return DVReadResult(
            interface=interface,
            host=host,
            elapsed_s=elapsed_s,
            dataset=dataset if dataset is not None else _dataset(),
        )

    def test_valid(self):
        r = self._result()
        assert r.interface == 'solarlog'
        assert r.elapsed_s == 0.5

    def test_elapsed_rounded(self):
        r = self._result(elapsed_s=0.123456789)
        d = r.model_dump()
        assert d['elapsed_s'] == 0.123

    def test_to_dict_is_flat(self):
        r = self._result()
        d = r.to_dict()
        assert 'production' in d
        assert 'interface' in d
        assert 'dataset' not in d

    def test_host_can_be_none(self):
        r = self._result(host=None)
        assert r.host is None

    def test_elapsed_must_be_non_negative(self):
        with pytest.raises(ValidationError):
            self._result(elapsed_s=-0.1)

    def test_read_at_is_set(self):
        r = self._result()
        assert r.read_at is not None

    def test_read_at_in_to_dict(self):
        r = self._result()
        d = r.to_dict()
        assert 'read_at' in d
        assert isinstance(d['read_at'], str)
        assert 'T' in d['read_at']  # ISO 8601

    def test_age_s_is_non_negative(self):
        r = self._result()
        assert r.age_s >= 0

    def test_age_s_increases(self):
        r = self._result()
        age1 = r.age_s
        time.sleep(0.05)
        age2 = r.age_s
        assert age2 > age1

    def test_is_stale_false_for_fresh(self):
        r = self._result()
        assert r.is_stale(max_age_s=60) is False

    def test_is_stale_true_for_old(self):
        r = self._result()
        time.sleep(0.05)
        assert r.is_stale(max_age_s=0.01) is True
