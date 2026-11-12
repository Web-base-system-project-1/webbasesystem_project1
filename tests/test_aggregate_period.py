"""Regression checks for the six-year injection baseline."""

from pipeline.aggregate_period import build_series


def test_baseline_counts_all_six_years_and_preserves_null_share():
    pair = {"domestic_id": "I1", "foreign_id": "I2", "field": "ai"}
    artifacts = {
        "collab_counts.csv": [
            {**pair, "year": 2015, "collab_count": 18},
            {**pair, "foreign_id": "I3", "year": 2020, "collab_count": 17},
        ],
        "kr_totals.csv": [
            {"domestic_id": "I1", "field": "ai", "year": 2015, "international_total": 18},
            {"domestic_id": "I1", "field": "ai", "year": 2020, "international_total": 17},
        ],
    }
    series, baselines, candidates = build_series(artifacts)
    assert len(series) == 22
    assert len(candidates) == 1
    assert candidates[0]["baseline_mean"] == 3
    assert baselines[1]["baseline_mean"] == 17 / 6
    missing_denominator = next(row for row in series if row["year"] == 2016)
    assert missing_denominator["collab_count"] == 0
    assert missing_denominator["share"] is None
    no_partner_papers = next(row for row in series if row["year"] == 2020 and row["foreign_id"] == "I2")
    assert no_partner_papers["share"] == 0
