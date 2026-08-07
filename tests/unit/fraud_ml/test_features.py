from services.fraud_ml.features import FEATURE_NAMES, MERCHANT_CATEGORIES, build_feature_row


def test_feature_row_length_matches_names():
    row = build_feature_row(amount_inr=1000, hour_of_day=10, is_failed=False, merchant_category="ECOM",
                             customer_mean_amount=500, customer_std_amount=100, velocity_24h=2, device_shared_count=0)
    assert len(row) == len(FEATURE_NAMES)


def test_one_hot_merchant_category_exactly_one_set():
    row = build_feature_row(amount_inr=1000, hour_of_day=10, is_failed=False, merchant_category="TRAVEL",
                             customer_mean_amount=500, customer_std_amount=100, velocity_24h=0, device_shared_count=0)
    mcat_start = FEATURE_NAMES.index("mcat_ECOM")
    mcat_values = row[mcat_start:mcat_start + len(MERCHANT_CATEGORIES)]
    assert sum(mcat_values) == 1
    assert mcat_values[MERCHANT_CATEGORIES.index("TRAVEL")] == 1


def test_zscore_zero_when_no_std():
    row = build_feature_row(amount_inr=1000, hour_of_day=10, is_failed=False, merchant_category="ECOM",
                             customer_mean_amount=500, customer_std_amount=0, velocity_24h=0, device_shared_count=0)
    zscore_idx = FEATURE_NAMES.index("amount_zscore")
    assert row[zscore_idx] == 0.0


def test_zscore_positive_when_above_mean():
    row = build_feature_row(amount_inr=2000, hour_of_day=10, is_failed=False, merchant_category="ECOM",
                             customer_mean_amount=500, customer_std_amount=100, velocity_24h=0, device_shared_count=0)
    zscore_idx = FEATURE_NAMES.index("amount_zscore")
    assert row[zscore_idx] == 15.0  # (2000-500)/100
