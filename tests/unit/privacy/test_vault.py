from services.privacy import vault


def test_encrypt_decrypt_roundtrip():
    plaintext = "ABCDE1234F"
    blob = vault.encrypt(plaintext)
    assert blob != plaintext
    assert vault.decrypt(blob) == plaintext


def test_store_and_retrieve(db):
    vault.store(db, "evt_test1__PAN_1", "PAN", "ABCDE1234F")
    db.flush()
    value = vault.retrieve(db, "evt_test1__PAN_1")
    assert value == "ABCDE1234F"


def test_retrieve_missing_token_returns_none(db):
    assert vault.retrieve(db, "does_not_exist_token") is None
