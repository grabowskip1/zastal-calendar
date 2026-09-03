from pathlib import Path

import pytest

from src import fiba, main, plk
from src.models import SourceError


def test_fetch_failure_never_writes(monkeypatch, tmp_path, games):
    target = tmp_path / 'calendar.ics'
    target.write_bytes(b'previous calendar bytes')
    monkeypatch.setattr(plk, 'fetch', lambda client: [g for g in games if g.source == 'plk'])

    def fail(client):
        raise SourceError('HTTP 503')

    monkeypatch.setattr(fiba, 'fetch', fail)
    with pytest.raises(SourceError):
        main.generate(target)
    assert target.read_bytes() == b'previous calendar bytes'


def test_plk_suspiciously_small_schedule(fixtures):
    class Client:
        def get(self, url):
            return (fixtures / 'plk_schedule.html').read_text()

    with pytest.raises(SourceError, match='Suspiciously few'):
        plk.fetch(Client())


def test_fiba_api_fallback(fixtures):
    class Client:
        def get(self, url, **kwargs):
            if 'digital-api.' in url:
                raise SourceError('HTTP 503')
            if url.endswith('/en/events'):
                return (fixtures / 'fiba_directory.html').read_text()
            if url.endswith('/games'):
                return (fixtures / 'fiba_games.html').read_text()
            return (fixtures / 'fiba_event.html').read_text() + (
                '<script>{"NEXT_CLIENT_APIM_SUBSCRIPTION_KEY":"test-only"}</script>')

    games = fiba.fetch(Client())
    assert len(games) == 5


def test_fiba_wrong_competition_fails(fiba_raw, fiba_info):
    fiba_raw[0]['competition']['competitionId'] = 123
    with pytest.raises(SourceError, match='another competition'):
        fiba.parse_games(fiba_raw, fiba_info)
