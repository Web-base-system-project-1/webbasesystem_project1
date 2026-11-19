"""Regression checks for the six-year injection baseline."""

from pipeline.aggregate_period import aggregate_countries, build_series


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


def test_country_counts_deduplicate_foreign_and_domestic_institutions():
    works = [{
        "work_id": "W1", "field": "ai", "year": 2015,
        "domestic_institutions": [{"id": "KR1"}, {"id": "KR2"}],
        "foreign_institutions": [
            {"id": "US1", "country_code": "US"}, {"id": "US2", "country_code": "US"},
            {"id": "GB1", "country_code": "GB"},
        ],
    }, {
        "work_id": "W2", "field": "ai", "year": 2016,
        "domestic_institutions": [{"id": "KR1"}],
        "foreign_institutions": [{"id": "GB1", "country_code": "GB"}],
    }]
    artifacts = {"kr_totals.csv": [
        {"domestic_id": domestic, "field": "ai", "year": year, "international_total": 1}
        for domestic, year in (("KR1", 2015), ("KR2", 2015), ("KR1", 2016))
    ]}
    output = aggregate_countries(works, artifacts)
    assert len(output["country_contributions.csv"]) == 5
    assert all(row["collab_count"] == 1 for row in output["country_counts.csv"])
    overview = {
        (row["country_code"], row["year"]): row for row in output["country_overview.csv"]
    }
    assert overview[("US", 2015)]["collab_count"] == 1
    assert overview[("US", 2015)]["international_total"] == 1
    assert overview[("US", 2016)]["share"] == 0
    assert overview[("US", 2017)]["share"] is None
    assert len(output["country_shares.csv"]) == 4 * 11
    assert aggregate_countries([], {"kr_totals.csv": []}) == {
        filename: [] for filename in output
    }
