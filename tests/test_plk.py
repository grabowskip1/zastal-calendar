from copy import deepcopy
from datetime import UTC, date, datetime
import json

import pytest

from src import plk
from src.models import SourceError


def test_full_schedule_scope_and_season(fixtures):
    season, games, links = plk.schedule_data((fixtures / 'plk_schedule.html').read_text())
    assert season == '2026/2027'
    assert len(games) == 3
    assert links['223461'].endswith('/223461/enea-laciate-astoria-bydgoszcz-vs-zastal-zielona-gora')


def test_away_game(plk_raw):
    game = plk.parse_game(plk_raw, '2026/2027')
    assert game.start == datetime(2026, 10, 3, 15, 30, tzinfo=UTC)
    assert game.away_is_zastal and not game.home_is_zastal
    assert game.summary.endswith(' – Zastal')
    assert game.uid == 'plk-223461@zastal-calendar'


def test_home_game(fixtures):
    raw = json.loads((fixtures / 'plk_223469.json').read_text())
    game = plk.parse_game(raw, '2026/2027')
    assert game.summary == '🏀 Zastal – Legia Warszawa'
    assert game.home_is_zastal


def test_midnight_means_tbd_local_date(fixtures):
    raw = json.loads((fixtures / 'plk_223493.json').read_text())
    game = plk.parse_game(raw, '2026/2027')
    assert game.start is None
    assert game.day == date(2026, 10, 31)  # UTC placeholder is previous day!


def test_time_change_same_uid(plk_raw):
    old = plk.parse_game(plk_raw, '2026/2027')
    plk_raw['dateLocal'] = '2026-10-04 19:00'
    plk_raw['date'] = '2026-10-04T17:00:00Z'
    new = plk.parse_game(plk_raw, '2026/2027')
    assert old.uid == new.uid and old.start != new.start


def test_venue_and_status(plk_raw):
    plk_raw.update(venue={'id':12, 'name':'Hala, Łódź', 'city':'Łódź'}, isFinished=True)
    game = plk.parse_game(plk_raw, '2026/2027')
    assert 'Hala, Łódź' in game.location and game.status == 'finished'
    plk_raw['isCancelled'] = True
    assert plk.parse_game(plk_raw, '2026/2027').status == 'cancelled'


def test_wrong_utc_is_rejected(plk_raw):
    plk_raw['date'] = '2026-10-03T17:30:00Z'
    with pytest.raises(SourceError):
        plk.parse_game(plk_raw, '2026/2027')


def test_css_changes_do_not_matter(fixtures):
    text = (fixtures / 'plk_schedule.html').read_text()
    assert plk.schedule_data(text) == plk.schedule_data(text.replace('<body>', '<body class="changed">'))


def test_detail_data_with_official_record(fixtures):
    raw = json.loads((fixtures / 'plk_detail.json').read_text())
    html = '<script type="application/json">' + json.dumps({'game': raw}) + '</script>'
    assert plk.detail_data(html, '223461') == raw
    with pytest.raises(SourceError):
        plk.detail_data(html, 'wrong-game')


def test_zero_html_error():
    with pytest.raises(SourceError):
        plk.schedule_data('<html>Temporarily unavailable</html>')


def test_supercup_is_not_obl(fixtures):
    html = (fixtures / 'plk_schedule.html').read_text()
    # Add a banner card which is deliberately outside the schedule object.
    banner = '<script type="application/json">' + json.dumps({
        'id': 'supercup', 'homeTeam': {'id':769}, 'guestTeam': {'id':123},
        'league': {'id': 99}, 'dateLocal': '2026-09-26 19:15'}) + '</script>'
    assert len(plk.schedule_data(html + banner)[1]) == 3
