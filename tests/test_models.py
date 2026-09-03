from datetime import UTC, date, datetime, time

import pytest

from src.models import SourceError, is_zastal, parse_date, parse_time, stable_id
from src.models import utc_datetime, verify_local


@pytest.mark.parametrize('name', ['Zastal Zielona Góra', 'ORLEN Zastal Zielona Góra',
                                 'Zastal Enea BC', 'Enea Zastal BC Zielona Gora'])
def test_sponsor_names(name):
    assert is_zastal(name, 'plk')


@pytest.mark.parametrize('name', ['SKM Zastal Zielona Góra', 'Zastal II Zielona Góra',
                                 'Stal Ostrów Wielkopolski', 'Legia Warszawa'])
def test_other_teams(name):
    assert not is_zastal(name, 'plk')


def test_ids_override_names():
    assert is_zastal('Future Sponsor', 'plk', 769)
    assert not is_zastal('Zastal Zielona Góra', 'plk', 123)
    assert is_zastal('Grono SA', 'fiba', 999, 10024)
    assert not is_zastal('Zastal', 'fiba', 285088, 123)
    assert is_zastal('Grono', 'fiba', 285088, known_team_ids={'285088'})


@pytest.mark.parametrize('value', ['2026-10-03', '03.10.2026'])
def test_dates(value):
    assert parse_date(value) == date(2026, 10, 3)


@pytest.mark.parametrize('value', ['2026-02-30', '10/11/26', 'TBD'])
def test_bad_dates(value):
    with pytest.raises(SourceError):
        parse_date(value)


@pytest.mark.parametrize('value', [None, '', 'TBD', 'TBA', '--:--'])
def test_tbd_times(value):
    assert parse_time(value) is None


def test_times_and_midnight():
    assert parse_time('20:15') == time(20, 15)
    assert parse_time('20:15:00') == time(20, 15)
    assert parse_time('00:00', midnight_is_tbd=True) is None
    assert parse_time('00:00') == time(0)
    with pytest.raises(SourceError):
        parse_time('25:61')


def test_utc_requires_evidence():
    with pytest.raises(SourceError):
        utc_datetime('2026-10-03T15:30:00')
    assert utc_datetime('2026-10-03T15:30:00', explicitly_utc=True).tzinfo == UTC


@pytest.mark.parametrize(('stamp', 'day', 'clock'), [
    ('2026-10-03T15:30:00Z', '2026-10-03', '17:30'),
    ('2026-12-03T16:30:00Z', '2026-12-03', '17:30'),
    ('2026-10-25T00:30:00Z', '2026-10-25', '02:30'),
    ('2026-10-25T01:30:00Z', '2026-10-25', '02:30'),
])
def test_warsaw_dst(stamp, day, clock):
    verify_local(utc_datetime(stamp), parse_date(day), parse_time(clock), 'Europe/Warsaw')


def test_mismatched_utc():
    with pytest.raises(SourceError):
        verify_local(utc_datetime('2026-10-03T17:30:00Z'), date(2026, 10, 3),
                     time(17, 30), 'Europe/Warsaw')


def test_stable_identity_fallback():
    assert stable_id(123, season='x', round_id=None, game_number=None) == '123'
    a = stable_id(None, season='2026/2027', round_id=1, game_number='002')
    assert a == stable_id(None, season='2026/2027', round_id=1, game_number='002')
    assert a != stable_id(None, season='2026/2027', round_id=2, game_number='002')
    with pytest.raises(SourceError):
        stable_id(None, season='2026/2027', round_id=1, game_number=None)
