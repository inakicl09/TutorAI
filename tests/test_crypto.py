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
