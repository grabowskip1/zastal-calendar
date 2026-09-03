'''Deterministic RFC 5545 output with versioned events and fail-closed updates.'''

from copy import deepcopy
from datetime import UTC, date, datetime, time, timedelta
import hashlib
import logging
import os
from pathlib import Path
import tempfile
from zoneinfo import ZoneInfo

from icalendar import Calendar, Event

from .models import Game, SourceError

LOG = logging.getLogger(__name__)
DURATION = timedelta(hours=2, minutes=15)
WARSAW = ZoneInfo('Europe/Warsaw')


def event_hash(event: Event) -> str:
    content = deepcopy(event)
    for name in ('DTSTAMP', 'LAST-MODIFIED', 'SEQUENCE', 'X-CONTENT-HASH'):
        content.pop(name, None)
    return hashlib.sha256(content.to_ical()).hexdigest()


def sort_key(event: Event) -> tuple[datetime, str]:
    start = event.decoded('DTSTART')
    if not isinstance(start, datetime):
        start = datetime.combine(start, time.min, WARSAW)
    return start.astimezone(UTC), str(event['UID'])


def make_event(game: Game) -> Event:
    game.validate()
    event = Event()
    event.add('uid', game.uid)
    event.add('dtstart', game.start if game.start else game.day)
    event.add('dtend', game.start + DURATION if game.start else game.day + timedelta(days=1))
    event.add('summary', game.summary)
    event.add('location', game.location)
    status_text = {'scheduled': 'Zaplanowany', 'finished': 'Zakończony', 'live': 'W trakcie',
                   'postponed': 'Przełożony — sprawdź nowy termin', 'cancelled': 'Odwołany',
                   'unconfirmed': 'Do potwierdzenia — sprawdź oficjalną stronę'}
    details = [game.competition, f'Sezon: {game.season}', game.phase,
               f'Gospodarze: {game.home}', f'Goście: {game.away}',
               f'Status: {status_text[game.status]}',
               f'Status źródłowy: {game.source_status}',
               f'ID źródłowe: {game.source_id}']
    if game.start:
        local = game.start.astimezone(ZoneInfo(game.timezone or 'UTC'))
        label = 'Czas UTC' if game.timezone == 'UTC' else 'Czas miejscowy'
        details += [f'{label}: {local:%Y-%m-%d %H:%M} ({game.timezone})',
                    'Przewidywany czas trwania: 2 godz. 15 min.']
    else:
        details += ['Godzina do ustalenia (TBD). Data również może się zmienić.']
    if not game.location:
        details += ['Hala: brak potwierdzonych danych w źródle.']
    if game.url:
        details += [f'Oficjalne źródło: {game.url}']
        event.add('url', game.url)
    event.add('description', '\n'.join(x for x in details if x))
    ics_status = 'CANCELLED' if game.status == 'cancelled' else (
        'TENTATIVE' if game.start is None or game.status in {'postponed', 'unconfirmed'} else 'CONFIRMED')
    event.add('status', ics_status)
    event.add('transp', 'TRANSPARENT')
    event.add('categories', [game.competition, 'Koszykówka', 'Zastal'])
    for key, value in {
        'X-SOURCE': game.source, 'X-SOURCE-ID': game.source_id, 'X-SEASON': game.season,
        'X-GAME-STATUS': game.status, 'X-SOURCE-STATUS': game.source_status,
        'X-SOURCE-TIMEZONE': game.timezone or 'TBD',
        'X-HOME-ID': game.home_id or 'TBD', 'X-AWAY-ID': game.away_id or 'TBD',
    }.items():
        event.add(key, value)
    return event


def validate_ics(data: bytes) -> Calendar:
    if not data or not data.endswith(b'END:VCALENDAR\r\n'):
        raise SourceError('ICS is empty or does not end with VCALENDAR/CRLF')
    if b'\n' in data.replace(b'\r\n', b'') or b'\r' in data.replace(b'\r\n', b''):
        raise SourceError('ICS must use CRLF line endings')
    if any(len(line) > 75 for line in data.split(b'\r\n')):
        raise SourceError('ICS line exceeds 75 octets')
    try:
        data.decode('utf-8')
        calendar = Calendar.from_ical(data)
        if calendar.name != 'VCALENDAR' or str(calendar.get('VERSION')) != '2.0':
            raise SourceError('Invalid iCalendar envelope/version')
        if not calendar.get('PRODID'):
            raise SourceError('Missing PRODID')
        events = calendar.walk('VEVENT')
        if not events:
            raise SourceError('ICS contains no events')
        uids = set()
        for event in events:
            if event.errors:
                raise SourceError(f'iCalendar parser errors: {event.errors}')
            for key in ('UID', 'DTSTAMP', 'DTSTART', 'DTEND', 'SUMMARY', 'LOCATION',
                        'DESCRIPTION', 'LAST-MODIFIED', 'SEQUENCE', 'STATUS',
                        'X-SOURCE', 'X-SOURCE-ID', 'X-SEASON', 'X-CONTENT-HASH'):
                if key not in event or isinstance(event[key], list):
                    raise SourceError(f'Missing/duplicate ICS property: {key}')
            uid = str(event['UID'])
            if uid in uids:
                raise SourceError(f'Duplicate UID: {uid}')
            uids.add(uid)
            if uid != f'{event["X-SOURCE"]}-{event["X-SOURCE-ID"]}@zastal-calendar':
                raise SourceError('UID does not match stable source identity')
            start, end = event.decoded('DTSTART'), event.decoded('DTEND')
            if type(start) is not type(end):
                raise SourceError('DTSTART/DTEND types differ')
            if isinstance(start, datetime):
                if start.tzinfo is None or end.tzinfo is None or end - start != DURATION:
                    raise SourceError('Invalid timed event timezone or duration')
            elif isinstance(start, date):
                if end - start != timedelta(days=1):
                    raise SourceError('Invalid all-day exclusive DTEND')
            else:
                raise SourceError('Invalid DTSTART type')
            for key in ('DTSTAMP', 'LAST-MODIFIED'):
                stamp = event.decoded(key)
                if not isinstance(stamp, datetime) or stamp.utcoffset() != timedelta(0):
                    raise SourceError(f'{key} must be UTC')
            if int(event['SEQUENCE']) < 0:
                raise SourceError('Negative SEQUENCE')
            if str(event['X-CONTENT-HASH']) != event_hash(event):
                raise SourceError(f'Event integrity check failed: {uid}')
        if events != sorted(events, key=sort_key):
            raise SourceError('ICS events are not chronologically sorted')
        return calendar
    except (ValueError, TypeError, KeyError, UnicodeError) as exc:
        if isinstance(exc, SourceError):
            raise
        raise SourceError(f'Invalid ICS: {exc}') from exc


def build_calendar(games: list[Game], previous: bytes | None = None,
                   now: datetime | None = None) -> bytes:
    if {g.source for g in games} != {'plk', 'fiba'}:
        raise SourceError('Both PLK and FIBA must succeed; previous calendar is preserved')
    old_events = validate_ics(previous).walk('VEVENT') if previous is not None else []
    old = {str(event['UID']): event for event in old_events}
    current: dict[str, Game] = {}
    signatures = set()
    for game in games:
        game.validate()
        if game.uid in current:
            raise SourceError(f'Duplicate UID: {game.uid}')
        signature = (game.source, game.season, game.home_id or game.home,
                     game.away_id or game.away, game.day)
        if signature in signatures:
            raise SourceError('Duplicate match with different source IDs')
        signatures.add(signature)
        current[game.uid] = game
    seasons = {(g.source, g.season) for g in games}
    for source in ('plk', 'fiba'):
        if len({g.season for g in games if g.source == source}) != 1:
            raise SourceError(f'Multiple current seasons returned by {source}')
        new_season = next(g.season for g in games if g.source == source)
        previous_seasons = [str(e['X-SEASON']) for e in old_events if str(e['X-SOURCE']) == source]
        if previous_seasons and new_season < max(previous_seasons):
            raise SourceError(f'Source season moved backwards: {source}')
    missing = [uid for uid, event in old.items()
               if (str(event['X-SOURCE']), str(event['X-SEASON'])) in seasons and uid not in current]
    if missing:
        raise SourceError(f'Previously known games disappeared; refusing destructive update: {missing}')
    now = (now or datetime.now(UTC)).astimezone(UTC).replace(microsecond=0)
    calendar = Calendar()
    calendar.add('prodid', '-//Zastal Calendar//PLK and FIBA//PL')
    calendar.add('version', '2.0')
    calendar.add('calscale', 'GREGORIAN')
    calendar.add('name', '🏀 Zastal Zielona Góra')
    calendar.add('x-wr-calname', '🏀 Zastal Zielona Góra')
    calendar.add('x-wr-timezone', 'Europe/Warsaw')
    calendar.add('x-wr-caldesc', 'Mecze Zastalu: ORLEN Basket Liga i FIBA Europe Cup')
    calendar.add('refresh-interval', timedelta(hours=6), parameters={'VALUE': 'DURATION'})
    calendar.add('x-published-ttl', 'PT6H')
    # Keep prior seasons. Absence is not evidence of cancellation.
    events = [deepcopy(e) for uid, e in old.items() if uid not in current]
    for game in games:
        event = make_event(game)
        digest = event_hash(event)
        prior = old.get(game.uid)
        if prior is not None and str(prior['X-CONTENT-HASH']) == digest:
            event = deepcopy(prior)
        else:
            modified = now
            if prior is not None:
                modified = max(modified, prior.decoded('LAST-MODIFIED') + timedelta(seconds=1))
            event.add('dtstamp', modified)
            event.add('last-modified', modified)
            event.add('sequence', int(prior['SEQUENCE']) + 1 if prior is not None else 0)
            event.add('x-content-hash', digest)
        events.append(event)
    for event in sorted(events, key=sort_key):
        calendar.add_component(event)
    data = calendar.to_ical()
    validate_ics(data)
    return data


def write_calendar(path: Path, games: list[Game], now: datetime | None = None) -> bool:
    previous = path.read_bytes() if path.exists() else None
    data = build_calendar(games, previous, now)
    if data == previous:
        LOG.info('Calendar unchanged: %s', path)
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    temp: str | None = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as handle:
            temp = handle.name
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temp, 0o644)
        os.replace(temp, path)
    finally:
        if temp and os.path.exists(temp):
            os.unlink(temp)
    LOG.info('Calendar updated atomically: %s (%d bytes)', path, len(data))
    return True
