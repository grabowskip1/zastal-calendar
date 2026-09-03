from datetime import UTC, datetime
import json
from pathlib import Path

import pytest

from src import fiba, plk

FIXTURES = Path(__file__).parent / 'fixtures'


@pytest.fixture
def fixtures():
    return FIXTURES


@pytest.fixture
def plk_raw():
    return json.loads((FIXTURES / 'plk_223461.json').read_text())


@pytest.fixture
def fiba_raw():
    return json.loads((FIXTURES / 'fiba_games.json').read_text())


@pytest.fixture
def fiba_info():
    return fiba.event_info((FIXTURES / 'fiba_event.html').read_text(),
                           'https://www.fiba.basketball/en/events/fiba-europe-cup-26-27')


@pytest.fixture
def games(fixtures, fiba_raw, fiba_info):
    season, raw, links = plk.schedule_data((fixtures / 'plk_schedule.html').read_text())
    return [plk.parse_game(r, season, links[str(r['id'])]) for r in raw] + fiba.parse_games(fiba_raw, fiba_info)


@pytest.fixture
def now():
    return datetime(2026, 9, 3, 12, 0, tzinfo=UTC)
