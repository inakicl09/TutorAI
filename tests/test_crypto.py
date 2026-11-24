from tutorai import crypto


def test_encrypt_then_decrypt_roundtrips():
    encrypted = crypto.encrypt_password("hunter2")

    assert encrypted != "hunter2"
    assert crypto.decrypt_password(encrypted) == "hunter2"


def test_key_is_generated_once_and_reused():
    first = crypto.encrypt_password("hunter2")
    second = crypto.encrypt_password("hunter2")

    # Fernet includes a random nonce, so ciphertexts differ even for the
    # same plaintext -- but both must decrypt back correctly with the
    # same (reused) key.
    assert crypto.decrypt_password(first) == "hunter2"
    assert crypto.decrypt_password(second) == "hunter2"


def test_decrypt_with_a_different_key_returns_none(monkeypatch, tmp_path):
    from tutorai import config

    encrypted = crypto.encrypt_password("secret")
    monkeypatch.setattr(config, "SECRET_KEY_PATH", str(tmp_path / "other.key"))

    assert crypto.decrypt_password(encrypted) is None


def test_secret_key_setting_overrides_the_key_file(monkeypatch):
    from cryptography.fernet import Fernet
    from tutorai import config

    monkeypatch.setattr(config, "SECRET_KEY", Fernet.generate_key().decode())
    encrypted = crypto.encrypt_password("secret")
    monkeypatch.setattr(config, "SECRET_KEY_PATH", "/nonexistent/should-not-be-used.key")

    assert crypto.decrypt_password(encrypted) == "secret"
