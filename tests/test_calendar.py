from dataclasses import replace
from datetime import UTC, date, datetime, timedelta

from icalendar import Calendar
import pytest

from src.calendar_writer import build_calendar, validate_ics, write_calendar
from src.models import SourceError


def events(data):
    return {str(e['UID']): e for e in Calendar.from_ical(data).walk('VEVENT')}


def test_valid_icalendar(games, now):
    data = build_calendar(games, now=now)
    result = validate_ics(data)
    assert len(result.walk('VEVENT')) == len(games)
    assert b'VERSION:2.0\r\n' in data
    assert b'PRODID:' in data
    assert b'REFRESH-INTERVAL;VALUE=DURATION:PT6H' in data
    assert b'METHOD:REQUEST' not in data


def test_unchanged_run_is_byte_identical(games, now):
    first = build_calendar(games, now=now)
    assert build_calendar(list(reversed(games)), previous=first,
                          now=now + timedelta(days=1)) == first


def test_changed_time_same_uid_and_increment_sequence(games, now):
    first = build_calendar(games, now=now)
    changed = replace(games[0], start=games[0].start + timedelta(hours=1))
    second = build_calendar([changed] + games[1:], first, now + timedelta(hours=6))
    a, b = events(first), events(second)
    assert set(a) == set(b)
    assert b[changed.uid].decoded('DTSTART') - a[changed.uid].decoded('DTSTART') == timedelta(hours=1)
    assert b[changed.uid]['SEQUENCE'] == 1
    assert b[games[1].uid].to_ical() == a[games[1].uid].to_ical()
    assert b[changed.uid].decoded('LAST-MODIFIED') > a[changed.uid].decoded('LAST-MODIFIED')


def test_tbd_becomes_timed_same_event(games, now):
    index = next(i for i, g in enumerate(games) if g.start is None and g.source == 'plk')
    before = build_calendar(games, now=now)
    game = games[index]
    replacement = replace(game, start=datetime(2026, 10, 31, 18, 0, tzinfo=UTC))
    changed = games[:index] + [replacement] + games[index + 1:]
    after = build_calendar(changed, before, now + timedelta(hours=6))
    assert type(events(before)[game.uid].decoded('DTSTART')) is date
    assert type(events(after)[game.uid].decoded('DTSTART')) is datetime
    assert events(after)[game.uid]['SEQUENCE'] == 1
    assert len(events(before)) == len(events(after))


def test_all_day_end_is_exclusive(games, now):
    data = build_calendar(games, now=now)
    for event in events(data).values():
        start = event.decoded('DTSTART')
        if type(start) is date:
            assert event.decoded('DTEND') == start + timedelta(days=1)
            assert event['STATUS'] == 'TENTATIVE'


def test_escaping_utf8_folding_and_polish(games, now):
    location = 'Hala; A, B \\ sektor\nŁódź — Żółć ' + 'Źąęśćńółźż' * 30
    game = replace(games[0], location=location)
    data = build_calendar([game] + games[1:], now=now)
    assert str(events(data)[game.uid]['LOCATION']) == location
    assert b'\\;' in data and b'\\,' in data and b'\\n' in data
    assert all(len(line) <= 75 for line in data.split(b'\r\n'))
    assert 'Zielona Góra' in data.decode()
    validate_ics(data)


def test_cancellation_keeps_event_and_uid(games, now):
    before = build_calendar(games, now=now)
    cancelled = replace(games[0], status='cancelled')
    after = build_calendar([cancelled] + games[1:], before, now)
    assert events(after)[cancelled.uid]['STATUS'] == 'CANCELLED'
    assert events(after)[cancelled.uid]['SEQUENCE'] == 1
    assert events(after)[cancelled.uid].decoded('LAST-MODIFIED') > now


def test_location_change_updates_sequence(games, now):
    before = build_calendar(games, now=now)
    changed = replace(games[0], location='Inna hala')
    after = build_calendar([changed] + games[1:], before, now)
    assert events(after)[changed.uid]['SEQUENCE'] == 1


def test_duplicates_rejected(games, now):
    with pytest.raises(SourceError, match='Duplicate UID'):
        build_calendar(games + [games[0]], now=now)
    with pytest.raises(SourceError, match='Duplicate match'):
        build_calendar(games + [replace(games[0], source_id='different-id')], now=now)


def test_missing_one_or_both_sources_preserves_file(tmp_path, games, now):
    output = tmp_path / 'calendar.ics'
    write_calendar(output, games, now)
    before = output.read_bytes()
    for subset in [[], [g for g in games if g.source == 'plk'], [g for g in games if g.source == 'fiba']]:
        with pytest.raises(SourceError):
            write_calendar(output, subset, now)
        assert output.read_bytes() == before


def test_disappearing_match_preserves_file(tmp_path, games, now):
    output = tmp_path / 'calendar.ics'
    write_calendar(output, games, now)
    before = output.read_bytes()
    with pytest.raises(SourceError, match='disappeared'):
        write_calendar(output, games[1:], now)
    assert output.read_bytes() == before


def test_old_season_retained_and_no_backward_season(games, now):
    before = build_calendar(games, now=now)
    next_games = [replace(g, source_id='next-' + g.source_id, season='2027/2028',
                          day=g.day.replace(year=g.day.year + 1),
                          start=g.start.replace(year=g.start.year + 1) if g.start else None)
                  for g in games]
    after = build_calendar(next_games, before, now)
    assert len(events(after)) == 2 * len(games)
    with pytest.raises(SourceError, match='backwards'):
        build_calendar(games, after, now)


def test_bad_existing_calendar_is_not_overwritten(tmp_path, games):
    output = tmp_path / 'calendar.ics'
    output.write_bytes(b'broken prior file')
    with pytest.raises(SourceError):
        write_calendar(output, games)
    assert output.read_bytes() == b'broken prior file'


def test_atomic_write_and_unchanged_mtime(tmp_path, games, now):
    output = tmp_path / 'calendar.ics'
    assert write_calendar(output, games, now)
    mtime = output.stat().st_mtime_ns
    assert not write_calendar(output, games, now + timedelta(hours=6))
    assert output.stat().st_mtime_ns == mtime
    assert list(tmp_path.iterdir()) == [output]


def test_failed_replace_preserves_old_file(monkeypatch, tmp_path, games, now):
    output = tmp_path / 'calendar.ics'
    write_calendar(output, games, now)
    before = output.read_bytes()

    def fail(*args):
        raise OSError('Simulated disk failure')

    monkeypatch.setattr('src.calendar_writer.os.replace', fail)
    with pytest.raises(OSError):
        write_calendar(output, [replace(games[0], location='New')] + games[1:], now)
    assert output.read_bytes() == before
    assert list(tmp_path.iterdir()) == [output]


def test_validator_rejects_lf_and_duplicate_uids(games, now):
    data = build_calendar(games, now=now)
    with pytest.raises(SourceError):
        validate_ics(data.replace(b'\r\n', b'\n'))
    calendar = Calendar.from_ical(data)
    calendar.add_component(calendar.walk('VEVENT')[0])
    with pytest.raises(SourceError, match='Duplicate UID'):
        validate_ics(calendar.to_ical())


def test_validator_detects_manual_tamper(games, now):
    data = build_calendar(games, now=now)
    with pytest.raises(SourceError, match='integrity'):
        validate_ics(data.replace(b'STATUS:CONFIRMED', b'STATUS:CANCELLED', 1))
