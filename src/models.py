'''Source-independent, validated game records and stable identities.'''

from dataclasses import dataclass
from datetime import UTC, date, datetime, time
import hashlib
import json
import re
import unicodedata
from zoneinfo import ZoneInfo


class SourceError(ValueError):
    '''The source is unavailable, incomplete, ambiguous or has changed schema.'''


def normalize_name(value: str) -> str:
    value = value.lower().replace('ł', 'l')
    return ' '.join(''.join(c for c in unicodedata.normalize('NFKD', value)
                           if not unicodedata.combining(c)).split())


def is_zastal(name: str, source: str, team_id: object = None,
              organisation_id: object = None, known_team_ids: set[str] | None = None) -> bool:
    '''IDs take precedence over sponsor-dependent names. No youth-team matching.'''
    if source == 'plk' and team_id is not None:
        return str(team_id) == '769'
    if source == 'fiba':
        if organisation_id is not None:
            return str(organisation_id) == '10024'
        if team_id is not None and known_team_ids:
            return str(team_id) in known_team_ids
    clean = normalize_name(name)
    return (bool(re.search(r'\bzastal\b', clean))
            and ('zielona gora' in clean or clean in {'zastal', 'zastal enea bc'})
            and not re.search(r'\b(skm|ii|iii|u\d+|junior)\b', clean))


def parse_date(value: str) -> date:
    for fmt in ('%Y-%m-%d', '%d.%m.%Y'):
        try:
            return datetime.strptime(value.strip(), fmt).date()
        except ValueError:
            pass
    raise SourceError(f'Unrecognized date: {value!r}')


def parse_time(value: str | None, *, midnight_is_tbd: bool = False) -> time | None:
    if value is None or value.strip().upper() in {'', 'TBD', 'TBA', '--:--', '-'}:
        return None
    try:
        result = time.fromisoformat(value.strip())
    except ValueError as exc:
        raise SourceError(f'Unrecognized time: {value!r}') from exc
    if result.tzinfo:
        raise SourceError('Expected a local clock time without an offset')
    return None if midnight_is_tbd and result == time(0) else result


def utc_datetime(value: str, *, explicitly_utc: bool = False) -> datetime:
    try:
        result = datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError as exc:
        raise SourceError(f'Invalid timestamp: {value!r}') from exc
    if result.tzinfo is None:
        if not explicitly_utc:
            raise SourceError('Timestamp does not specify a timezone')
        result = result.replace(tzinfo=UTC)
    return result.astimezone(UTC)


def verify_local(instant: datetime, day: date, clock: time, timezone: str) -> None:
    '''Validate UTC against wall time, including DST; never guess an offset.'''
    try:
        actual = instant.astimezone(ZoneInfo(timezone))
    except (KeyError, ValueError) as exc:
        raise SourceError(f'Unknown IANA timezone: {timezone}') from exc
    if actual.date() != day or actual.time().replace(tzinfo=None) != clock:
        raise SourceError(f'UTC/local time disagreement: {instant}, {day} {clock}, {timezone}')


def stable_id(source_id: object, *, season: str, round_id: object,
              game_number: object) -> str:
    if source_id is not None and str(source_id).strip():
        value = str(source_id)
        if not re.fullmatch(r'[A-Za-z0-9_-]+', value):
            raise SourceError('Unsafe source game ID')
        return value
    if not season or round_id in (None, '') or game_number in (None, ''):
        raise SourceError('No stable ID or unambiguous round/game-number fallback')
    key = json.dumps([season, str(round_id), str(game_number)], ensure_ascii=False)
    return 'fallback-' + hashlib.sha256(key.encode()).hexdigest()[:32]


@dataclass(frozen=True)
class Game:
    source: str
    source_id: str
    competition: str
    season: str
    home: str
    away: str
    home_id: str | None
    away_id: str | None
    home_is_zastal: bool
    away_is_zastal: bool
    day: date
    start: datetime | None
    timezone: str | None
    location: str
    status: str
    source_status: str
    url: str
    phase: str = ''

    @property
    def uid(self) -> str:
        return f'{self.source}-{self.source_id}@zastal-calendar'

    @property
    def summary(self) -> str:
        home = 'Zastal' if self.home_is_zastal else self.home
        away = 'Zastal' if self.away_is_zastal else self.away
        return f'{home} – {away}'

    def validate(self) -> None:
        if self.home_is_zastal == self.away_is_zastal:
            raise SourceError(f'Expected exactly one Zastal team: {self.uid}')
        if not self.home or not self.away or not self.season or not self.source_id:
            raise SourceError(f'Incomplete game: {self.uid}')
        if self.start and (self.start.tzinfo is None or not self.timezone):
            raise SourceError(f'Timed game without timezone: {self.uid}')
        if self.status not in {'scheduled', 'finished', 'live', 'postponed', 'cancelled', 'unconfirmed'}:
            raise SourceError(f'Unknown game status: {self.status}')
