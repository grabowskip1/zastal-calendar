'''FIBA: website JSON API, with official embedded JSON as a fallback.'''

from dataclasses import dataclass
import json
import logging
import re
from typing import Any
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from .http_client import HttpClient
from .models import Game, SourceError, is_zastal, parse_date, parse_time, stable_id
from .models import utc_datetime, verify_local
from .structured import flight_text, records

EVENTS_URL = 'https://www.fiba.basketball/en/events'
API_URL = 'https://digital-api.fiba.basketball/hapi/getgdapgamesbycompetitionid'
LOG = logging.getLogger(__name__)


@dataclass(frozen=True)
class EventInfo:
    url: str
    competition_id: str
    season: str
    team_ids: frozenset[str]


def discover_event(html: str) -> str:
    candidates: dict[tuple[int, int], str] = {}
    for tag in BeautifulSoup(html, 'html.parser').find_all('a', href=True):
        url = urljoin(EVENTS_URL, tag['href']).rstrip('/')
        match = re.fullmatch(r'/en/events/fiba-europe-cup-(\d{2})-(\d{2})', urlparse(url).path)
        if match and urlparse(url).hostname in {'www.fiba.basketball', 'fiba.basketball'}:
            years = (2000 + int(match[1]), 2000 + int(match[2]))
            if years[1] != years[0] + 1:
                raise SourceError('Unexpected FIBA edition slug')
            candidates[years] = url
    if not candidates:
        raise SourceError('No FIBA Europe Cup edition in the official event directory')
    # Only editions actually linked by FIBA are eligible; never synthesize a season URL.
    return candidates[max(candidates)]


def event_info(html: str, url: str) -> EventInfo:
    rows = records(html)
    slug = url.rstrip('/').rsplit('/', 1)[1]
    candidates = [x for x in rows if x.get('slug') == slug and x.get('fibaSourceDatas')]
    if not candidates or any(x['fibaSourceDatas'] != candidates[0]['fibaSourceDatas']
                             for x in candidates):
        raise SourceError('FIBA competition metadata is missing or ambiguous')
    source = candidates[0]['fibaSourceDatas']
    if source.get('competitionCode') != 'ECM2':
        raise SourceError('Wrong FIBA competition')
    start_year = parse_date(source['start'][:10]).year
    end_year = parse_date(source['end'][:10]).year
    if end_year != start_year + 1 or int(source['season']) != end_year:
        raise SourceError('FIBA season metadata is inconsistent')
    if slug != f'fiba-europe-cup-{start_year % 100:02}-{end_year % 100:02}':
        raise SourceError('FIBA URL and metadata disagree about season')
    team_ids = frozenset(str(x['teamId']) for x in rows if x.get('teamId') is not None
                         and str(x.get('organisationId')) == '10024')
    if not team_ids:
        raise SourceError('Zastal organisation 10024 not found in FIBA edition')
    return EventInfo(url, str(source['competitionId']), f'{start_year}/{end_year}', team_ids)


def client_key(html: str) -> str:
    # Public website client configuration; no credential is hardcoded or logged.
    text = html + '\n' + flight_text(html)
    match = re.search(r'"NEXT_CLIENT_APIM_SUBSCRIPTION_KEY"\s*:\s*"([^"\s]+)"', text)
    if not match:
        raise SourceError('FIBA public website client configuration unavailable')
    return match[1]


def embedded_games(html: str) -> list[dict[str, Any]]:
    arrays = [x['games'] for x in records(html) if isinstance(x.get('games'), list)
              and x['games'] and all(isinstance(g, dict) and 'gameId' in g for g in x['games'])]
    if len(arrays) != 1:
        raise SourceError('FIBA full embedded game list missing or ambiguous')
    return arrays[0]


def parse_games(raw_games: Any, info: EventInfo) -> list[Game]:
    if not isinstance(raw_games, list) or not raw_games:
        raise SourceError('FIBA API/embedded list is empty or not a list')
    games = []
    seen = set()
    for raw in raw_games:
        if not isinstance(raw, dict) or not {'teamA', 'teamB', 'competition'} <= raw.keys():
            raise SourceError('FIBA game schema changed')
        if str(raw['competition'].get('competitionId')) != info.competition_id:
            raise SourceError('FIBA returned games from another competition')
        if str(raw['competition'].get('season')) != info.season.split('/')[1]:
            raise SourceError('FIBA returned games from another season')
        home, away = raw['teamA'] or {}, raw['teamB'] or {}

        def matches(team: dict[str, Any]) -> bool:
            return is_zastal(team.get('shortName') or team.get('officialName', ''), 'fiba',
                             team.get('teamId'), team.get('organisationId'), set(info.team_ids))

        if not (matches(home) or matches(away)):
            continue
        source_id = stable_id(raw.get('gameId'), season=info.season,
                              round_id=raw.get('round', {}).get('roundId'),
                              game_number=raw.get('gameName'))
        if source_id in seen:
            raise SourceError(f'Duplicate FIBA game: {source_id}')
        seen.add(source_id)
        local = str(raw.get('gameDateTime') or '')
        if not local:
            raise SourceError(f'FIBA date is TBD; cannot safely place game {source_id}')
        day = parse_date(local[:10])
        if day.year not in {int(x) for x in info.season.split('/')}:
            raise SourceError('FIBA game date outside selected season')
        has_time = raw.get('hasTimeGameDateTime')
        if not isinstance(has_time, bool):
            raise SourceError('FIBA hasTimeGameDateTime flag missing')
        zone = raw.get('ianaTimeZone')
        start = None
        if has_time:
            clock = parse_time(local[11:])
            if clock is None:
                raise SourceError('FIBA says a time exists, but it is empty')
            # The API field is explicitly UTC, despite omitting the trailing Z.
            start = utc_datetime(raw['gameDateTimeUTC'], explicitly_utc=True)
            if zone:
                verify_local(start, day, clock, zone)
            else:
                # Do not infer a host zone from the away team's country.
                zone = 'UTC'
        raw_status = str(raw.get('statusCode', ''))
        mapping = {'INIT': 'scheduled', 'N': 'scheduled', 'VALID': 'finished',
                   'CLOS': 'finished', 'PROGR': 'live', 'CONFL': 'unconfirmed',
                   'CANCEL': 'cancelled', 'DEL': 'cancelled'}
        if raw_status not in mapping:
            raise SourceError(f'Unknown FIBA status code: {raw_status}')
        status = mapping[raw_status]
        if raw.get('isPostponed') and status != 'cancelled':
            status = 'postponed'
        # Match the official route, but avoid unpublished placeholder detail pages.
        # FIBA's numeric-only route can return HTTP 200 with Content Unavailable.
        url = f'{info.url}/games'
        if raw.get('gameId') is not None and home.get('code') and away.get('code'):
            home_code, away_code = home['code'], away['code']
            url += f'/{source_id}-{home_code}-{away_code}'
        game = Game(
            source='fiba', source_id=source_id, competition='FIBA Europe Cup', season=info.season,
            home=home.get('shortName') or home.get('officialName') or 'Rywal do ustalenia',
            away=away.get('shortName') or away.get('officialName') or 'Rywal do ustalenia',
            home_id=str(home['teamId']) if home.get('teamId') is not None else None,
            away_id=str(away['teamId']) if away.get('teamId') is not None else None,
            home_is_zastal=matches(home), away_is_zastal=matches(away), day=day,
            start=start, timezone=zone,
            location=', '.join(str(raw[k]) for k in ('venueName', 'hostCity', 'hostCountry')
                               if raw.get(k)), status=status, source_status=raw_status, url=url,
            phase=' · '.join(str(x) for x in [raw.get('round', {}).get('roundName'),
                                             raw.get('groupPairingCode')] if x),
        )
        game.validate()
        games.append(game)
    if not games:
        raise SourceError('FIBA returned zero Zastal games')
    return games


def fetch(client: HttpClient) -> list[Game]:
    url = discover_event(client.get(EVENTS_URL))
    html = client.get(url)
    info = event_info(html, url)
    try:
        payload = client.get(f'{API_URL}?gdapCompetitionId={info.competition_id}',
                             headers={'Ocp-Apim-Subscription-Key': client_key(html)})
        games = parse_games(json.loads(payload), info)
        LOG.info('FIBA transport: official website JSON API')
    except (SourceError, ValueError, KeyError, TypeError) as exc:
        LOG.warning('FIBA API failed (%s); trying official embedded JSON', type(exc).__name__)
        games = parse_games(embedded_games(client.get(f'{url}/games')), info)
    if len(games) < 2:
        raise SourceError(f'Suspiciously few FIBA games: {len(games)} (minimum 2)')
    LOG.info('FIBA %s, competition %s: %d Zastal games', info.season, info.competition_id, len(games))
    return games
