'''PLK: authoritative schedule JSON in server-rendered Next.js HTML.'''

from concurrent.futures import ThreadPoolExecutor
import logging
import re
from typing import Any
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from .http_client import HttpClient
from .models import Game, SourceError, is_zastal, parse_date, parse_time, stable_id
from .models import utc_datetime, verify_local
from .structured import records, walk

SCHEDULE_URL = 'https://plk.pl/terminarz'
LOG = logging.getLogger(__name__)


def schedule_data(html: str) -> tuple[str, list[dict[str, Any]], dict[str, str]]:
    rows = records(html)
    current = {str(x['currentSeasonId']) for x in rows if x.get('currentSeasonId')}
    if len(current) != 1:
        raise SourceError('PLK current season is missing or ambiguous')
    season_id = current.pop()
    names = {x['name'] for x in rows if str(x.get('id')) == season_id
             and re.fullmatch(r'\d{4}/\d{4}', str(x.get('name', '')))}
    if len(names) != 1:
        raise SourceError('PLK season name cannot be verified')
    season = names.pop()
    schedules = [x['schedule'] for x in rows if isinstance(x.get('schedule'), list)]
    if len(schedules) != 1:
        raise SourceError('PLK full schedule is missing or ambiguous')
    games = [x for x in walk(schedules[0]) if {'homeTeam', 'guestTeam', 'dateLocal'} <= x.keys()
             and str(x.get('league', {}).get('id')) == '2']
    if not games:
        raise SourceError('PLK returned zero games (HTTP 200 is not enough)')
    selected = []
    for game in games:
        if str(game.get('seasonId')) != season_id:
            raise SourceError('PLK mixed or stale season data')
        if any(is_zastal(game[k].get('name', ''), 'plk', game[k].get('id'))
               for k in ('homeTeam', 'guestTeam')):
            selected.append(game)
    # ID absence is allowed only if the explicit structural fallback exists.
    ids = [stable_id(x.get('id'), season=season, round_id=x.get('round', {}).get('id'),
                     game_number=x.get('gameNo')) for x in selected]
    if len(ids) != len(set(ids)):
        raise SourceError('Duplicate PLK game IDs')
    links = {}
    for tag in BeautifulSoup(html, 'html.parser').find_all('a', href=True):
        match = re.search(r'/mecz/(\d+)(?:/|$)', tag['href'])
        if match:
            links[match[1]] = urljoin(SCHEDULE_URL, tag['href'])
    return season, selected, links


def detail_data(html: str, source_id: str) -> dict[str, Any]:
    candidates = [x for x in records(html) if str(x.get('id')) == source_id
                  and {'venue', 'homeTeam', 'guestTeam', 'dateLocal'} <= x.keys()]
    if not candidates or any(x != candidates[0] for x in candidates):
        raise SourceError(f'PLK match detail missing or inconsistent: {source_id}')
    return candidates[0]


def parse_game(raw: dict[str, Any], season: str, url: str = '') -> Game:
    home, away = raw['homeTeam'], raw['guestTeam']
    parts = str(raw['dateLocal']).split()
    if not 1 <= len(parts) <= 2:
        raise SourceError('PLK invalid dateLocal')
    day = parse_date(parts[0])
    clock = parse_time(parts[1] if len(parts) == 2 else None, midnight_is_tbd=True)
    start = None
    if clock is not None:
        start = utc_datetime(raw['date'])
        verify_local(start, day, clock, 'Europe/Warsaw')
    if day.year not in {int(x) for x in season.split('/')}:
        raise SourceError('PLK date is outside the selected season')
    status = 'finished' if raw.get('isFinished') is True else 'scheduled'
    if not isinstance(raw.get('isFinished'), bool):
        raise SourceError('PLK isFinished flag is missing')
    if raw.get('isPostponed'):
        status = 'postponed'
    if raw.get('isCancelled') or raw.get('isCanceled'):
        status = 'cancelled'
    venue = raw.get('venue') or {}
    location = ', '.join(str(venue[k]) for k in ('name', 'city', 'address') if venue.get(k))
    source_id = stable_id(raw.get('id'), season=season,
                          round_id=raw.get('round', {}).get('id'), game_number=raw.get('gameNo'))
    game = Game(
        source='plk', source_id=source_id, competition='ORLEN Basket Liga', season=season,
        home=raw.get('homeTeamName') or home['name'],
        away=raw.get('guestTeamName') or away['name'],
        home_id=str(home['id']) if home.get('id') is not None else None,
        away_id=str(away['id']) if away.get('id') is not None else None,
        home_is_zastal=is_zastal(home.get('name', ''), 'plk', home.get('id')),
        away_is_zastal=is_zastal(away.get('name', ''), 'plk', away.get('id')),
        day=day, start=start, timezone='Europe/Warsaw', location=location,
        status=status, source_status=status, url=url,
        phase=' · '.join(x['name'] for x in (raw.get('round', {}), raw.get('queue', {}))
                         if x.get('name')),
    )
    game.validate()
    return game


def fetch(client: HttpClient) -> list[Game]:
    season, raw_games, links = schedule_data(client.get(SCHEDULE_URL))
    if len(raw_games) < 20:
        raise SourceError(f'Suspiciously few PLK games: {len(raw_games)} (minimum 20)')

    def enrich(raw: dict[str, Any]) -> Game:
        identity = str(raw.get('id', ''))
        url = links.get(identity, '')
        if identity and not url:
            raise SourceError(f'PLK official game link missing: {identity}')
        if url:
            detail = detail_data(client.get(url), identity)
            if (str(detail.get('seasonId')) != str(raw['seasonId'])
                    or str(detail.get('league', {}).get('id')) != '2'):
                raise SourceError('PLK detail belongs to a different season or competition')
            raw = detail
        return parse_game(raw, season, url)

    with ThreadPoolExecutor(max_workers=4) as pool:
        games = list(pool.map(enrich, raw_games))
    LOG.info('PLK %s: %d Zastal games', season, len(games))
    return games
