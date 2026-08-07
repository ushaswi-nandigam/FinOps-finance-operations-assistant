from services.privacy.recognizers import find_pii, luhn_valid, verhoeff_checksum_valid


def _valid_aadhaar() -> str:
    # Brute-force a 12-digit string whose last digit makes the Verhoeff
    # checksum valid, so the test doesn't depend on a hardcoded real-looking
    # number being coincidentally valid.
    for last in range(10):
        candidate = f"23456789012{last}"
        if verhoeff_checksum_valid(candidate):
            return candidate
    raise AssertionError("no valid checksum found")


def test_pan_detected():
    matches = find_pii("My PAN is ABCDE1234F for verification")
    labels = [m.label for m in matches]
    assert "PAN" in labels


def test_email_detected_not_double_counted_as_upi():
    matches = find_pii("Contact me at user@example.com please")
    labels = [m.label for m in matches]
    assert labels.count("EMAIL") == 1
    assert "UPI" not in labels


def test_upi_vpa_detected():
    matches = find_pii("Pay to my UPI ID ramesh@okhdfcbank today")
    labels = [m.label for m in matches]
    assert "UPI" in labels


def test_ifsc_detected():
    matches = find_pii("Branch IFSC is HDFC0001234 for the transfer")
    labels = [m.label for m in matches]
    assert "IFSC" in labels


def test_card_number_luhn_validated():
    valid_card = "4539578763621486"  # passes Luhn
    invalid_card = "1234567890123456"  # fails Luhn
    assert luhn_valid(valid_card)
    assert not luhn_valid(invalid_card)

    matches = find_pii(f"My card {valid_card} was charged twice")
    assert any(m.label == "CARD" for m in matches)

    matches2 = find_pii(f"Random number {invalid_card} appears here")
    assert not any(m.label == "CARD" for m in matches2)


def test_aadhaar_checksum_validated():
    aadhaar = _valid_aadhaar()
    matches = find_pii(f"My Aadhaar number is {aadhaar} for KYC")
    assert any(m.label == "AADHAAR" for m in matches)


def test_phone_detected():
    matches = find_pii("Call me on 9876543210 anytime")
    labels = [m.label for m in matches]
    assert "PHONE" in labels


def test_overlapping_matches_resolved_without_crash():
    text = "PAN ABCDE1234F, email a@b.com, phone 9876543210, IFSC HDFC0001234"
    matches = find_pii(text)
    # No two selected matches should overlap
    for i in range(len(matches) - 1):
        assert matches[i].end <= matches[i + 1].start
