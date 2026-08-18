from unittest import mock
from compass.services import recommendation

BACKTICK = chr(96)


def test_generate_daily_uses_correct_column_mapping():
    captured = []

    def fake_select_many(sql, *a, **k):
        captured.append(sql)
        return ([], [])

    class FakeDB:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def select_many(self, sql, *a, **k):
            return fake_select_many(sql, *a, **k)

        def execute(self, sql, *a, **k):
            captured.append(sql)
            return None

        def commit(self, *a, **k):
            return None

        def rollback(self, *a, **k):
            return None

        def close(self, *a, **k):
            return None

    with mock.patch.object(recommendation, 'Database', FakeDB):
        svc = recommendation.RecommendationService()
        svc.generate_daily(target_date='2026-08-18')

    joined = '\n'.join(captured)
    assert 'pe_ratio_dynamic' in joined
    assert 'pb_ratio' in joined


def test_rank_column_is_backticked_reserved_word():
    src = open(recommendation.__file__, encoding='utf-8').read()
    assert (BACKTICK + 'rank' + BACKTICK) in src
    assert 'rank=VALUES(rank)' not in src
