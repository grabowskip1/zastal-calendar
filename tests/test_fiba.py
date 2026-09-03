from copy import deepcopy
from datetime import UTC, date, datetime

import pytest

from src import fiba
from src.models import SourceError


def test_discover_actual_edition(fixtures):
    html = (fixtures / 'fiba_directory.html').read_text()
    assert fiba.discover_event(html).endswith('fiba-europe-cup-26-27')
    # An unpublished calendar-year guess must not be generated.
    assert fiba.discover_event(html.replace('26-27', '27-28')).endswith('27-28')


def test_metadata_organization_identity(fiba_info):
    assert fiba_info.season == '2026/2027'
    assert fiba_info.competition_id == '209129'
    assert fiba_info.team_ids == {'285088'}


def test_official_api_and_embedded_data_agree(fixtures, fiba_raw, fiba_info):
    embedded = fiba.embedded_games((fixtures / 'fiba_games.html').read_text())
    assert fiba.parse_games(embedded, fiba_info) == fiba.parse_games(fiba_raw, fiba_info)


def test_utc_field_and_foreign_zone(fiba_raw, fiba_info):
    game = fiba.parse_games(fiba_raw, fiba_info)[0]
    assert game.start == datetime(2026, 10, 6, 16, 0, tzinfo=UTC)
    assert game.timezone == 'Europe/Budapest'
    assert game.summary.endswith(' – Zastal')


def test_tbd_opponent_preserves_game_id(fiba_raw, fiba_info):
    before = fiba.parse_games(fiba_raw, fiba_info)[1]
    assert before.start is None and before.home_is_zastal
    assert before.away == 'Rywal do ustalenia'
    assert before.url == f'{fiba_info.url}/games'
    fiba_raw[1]['teamB'] = {'teamId':987, 'organisationId':321, 'code':'NEW', 'shortName':'Nowy rywal'}
    after = fiba.parse_games(fiba_raw, fiba_info)[1]
    assert before.uid == after.uid and before.away != after.away
    assert after.url.endswith('/135699-ZIE-NEW')


def test_unlocated_away_tbd(fiba_raw, fiba_info):
    game = fiba.parse_games(fiba_raw, fiba_info)[3]
    assert game.day == date(2026, 11, 18) and game.timezone is None and game.start is None
    assert game.home == 'Rywal do ustalenia'


def test_real_midnight_is_not_tbd(fiba_raw, fiba_info):
    raw = fiba_raw[0]
    raw.update(gameDateTime='2026-10-06T00:00:00', gameDateTimeUTC='2026-10-05T22:00:00')
    assert fiba.parse_games(fiba_raw, fiba_info)[0].start is not None


def test_timezone_not_assumed_polish(fiba_raw, fiba_info):
    raw = fiba_raw[0]
    raw.update(ianaTimeZone='Europe/Istanbul', gameDateTime='2026-10-06T19:00:00')
    assert fiba.parse_games(fiba_raw, fiba_info)[0].start.hour == 16


@pytest.mark.parametrize('flag', [None, 'false', 0])
def test_tbd_boolean_required(fiba_raw, fiba_info, flag):
    fiba_raw[0]['hasTimeGameDateTime'] = flag
    with pytest.raises(SourceError):
        fiba.parse_games(fiba_raw, fiba_info)


@pytest.mark.parametrize(('code', 'expected'), [('VALID','finished'), ('PROGR','live'),
                                                ('CANCEL','cancelled'), ('DEL','cancelled'),
                                                ('CONFL','unconfirmed')])
def test_status_codes(fiba_raw, fiba_info, code, expected):
    fiba_raw[0]['statusCode'] = code
    assert fiba.parse_games(fiba_raw, fiba_info)[0].status == expected


def test_unknown_status_fails(fiba_raw, fiba_info):
    fiba_raw[0]['statusCode'] = 'NEW_SCHEMA'
    with pytest.raises(SourceError):
        fiba.parse_games(fiba_raw, fiba_info)


def test_duplicate_api_rows_fail(fiba_raw, fiba_info):
    with pytest.raises(SourceError):
        fiba.parse_games(fiba_raw + [fiba_raw[0]], fiba_info)


def test_empty_source_fails(fiba_info):
    with pytest.raises(SourceError):
        fiba.parse_games([], fiba_info)


def test_public_key_not_hardcoded():
    html = '<script>window.config={"NEXT_CLIENT_APIM_SUBSCRIPTION_KEY":"rotated-test-key"}</script>'
    assert fiba.client_key(html) == 'rotated-test-key'
