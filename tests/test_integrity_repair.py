from dataclasses import replace
from datetime import timedelta

from icalendar import Calendar
import pytest

from src.calendar_writer import build_calendar, validate_ics, write_calendar
from src.models import SourceError


def tamper(data: bytes) -> tuple[bytes, str]:
    calendar = Calendar.from_ical(data)
    event = calendar.walk('VEVENT')[0]
    uid = str(event['UID'])
    event['SUMMARY'] = 'Manually edited title'
    return calendar.to_ical(), uid


def index(data: bytes) -> dict:
    return {str(e['UID']): e for e in Calendar.from_ical(data).walk('VEVENT')}


def test_explicit_repair_restores_source_and_preserves_versions(games, now):
    original = build_calendar(games, now=now)
    damaged, uid = tamper(original)
    with pytest.raises(SourceError, match='integrity'):
        build_calendar(games, damaged, now)
    repaired = build_calendar(games, damaged, now, repair_integrity=True)
    validate_ics(repaired)
    old, new = index(original), index(repaired)
    assert new.keys() == old.keys()
    assert str(new[uid]['SUMMARY']) == str(old[uid]['SUMMARY'])
    # The stored old hash already matches the source. Still rebuild edited content.
    assert new[uid]['SEQUENCE'] == old[uid]['SEQUENCE'] + 1
    assert new[uid].decoded('LAST-MODIFIED') > old[uid].decoded('LAST-MODIFIED')
    for unchanged in old.keys() - {uid}:
        assert old[unchanged].to_ical() == new[unchanged].to_ical()
    assert build_calendar(games, repaired, now + timedelta(hours=6)) == repaired


def test_repair_valid_calendar_is_noop(games, now):
    data = build_calendar(games, now=now)
    assert build_calendar(games, data, now, repair_integrity=True) == data


def test_repair_requires_both_sources_and_preserves_file(tmp_path, games, now):
    data, _ = tamper(build_calendar(games, now=now))
    path = tmp_path / 'calendar.ics'
    path.write_bytes(data)
    with pytest.raises(SourceError, match='Both PLK and FIBA'):
        write_calendar(path, [g for g in games if g.source == 'plk'], repair_integrity=True)
    assert path.read_bytes() == data


def test_repair_does_not_accept_duplicate_uids(games, now):
    calendar = Calendar.from_ical(build_calendar(games, now=now))
    calendar.add_component(calendar.walk('VEVENT')[0])
    with pytest.raises(SourceError, match='Duplicate UID'):
        build_calendar(games, calendar.to_ical(), now, repair_integrity=True)


def test_repair_refuses_historical_record_without_source(games, now):
    previous, _ = tamper(build_calendar(games, now=now))
    next_season = [replace(g, season='2027/2028', source_id='next-' + g.source_id,
                           day=g.day.replace(year=g.day.year + 1),
                           start=g.start.replace(year=g.start.year + 1) if g.start else None)
                   for g in games]
    with pytest.raises(SourceError, match='absent from current sources'):
        build_calendar(next_season, previous, now, repair_integrity=True)


def test_repair_refuses_malformed_ics(games, now):
    with pytest.raises(SourceError):
        build_calendar(games, b'not an ICS file', now, repair_integrity=True)
