from datetime import date

from nhl_pxp.scraper import NHLPxpScraper


class FakeApi:
    def get_game_ids_for_date(self, game_date):
        return [2007020001]

    def get_game_log(self, game_id):
        return {
            "gameData": {"datetime": {"dateTime": "2007-10-03T23:00:00Z"}, "game": {}, "teams": {}},
            "liveData": {"plays": {"allPlays": []}},
        }


class FakeRepo:
    def __init__(self, exists=False):
        self.exists = exists
        self.saved = 0

    def initialize_schema(self):
        pass

    def game_exists(self, game_id):
        return self.exists

    def upsert_game_and_events(self, game_id, payload):
        self.saved += 1


def test_scraper_skips_existing_games():
    scraper = NHLPxpScraper(api=FakeApi(), repository=FakeRepo(exists=True))
    stats = scraper.backfill(date(2007, 10, 3), date(2007, 10, 3), skip_existing=True)

    assert stats.games_skipped_existing == 1
    assert stats.games_inserted_or_updated == 0


def test_scraper_saves_when_not_existing():
    repo = FakeRepo(exists=False)
    scraper = NHLPxpScraper(api=FakeApi(), repository=repo)
    stats = scraper.backfill(date(2007, 10, 3), date(2007, 10, 3), skip_existing=True)

    assert stats.games_inserted_or_updated == 1
    assert repo.saved == 1
