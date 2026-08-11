import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from auth import hash_password, verify_password


def test_hash_and_verify_round_trip():
    password_hash = hash_password("hi")
    assert verify_password("hi", password_hash) is True


def test_hash_is_not_plaintext():
    password_hash = hash_password("hunter2")
    assert password_hash != "hunter2"


def test_verify_rejects_wrong_password():
    password_hash = hash_password("correct-horse")
    assert verify_password("wrong-horse", password_hash) is False


def test_hash_and_verify_short_password():
    # Regression: passlib 1.7.4 + bcrypt>=4.1 misfired a "72 bytes" error
    # even on trivially short passwords -- this must round-trip cleanly.
    password_hash = hash_password("ab")
    assert verify_password("ab", password_hash) is True


def test_hash_and_verify_long_password_does_not_raise():
    # bcrypt itself hard-caps passwords at 72 bytes and raises past that --
    # auth.py truncates consistently on both sides so this doesn't crash.
    long_password = "x" * 100
    password_hash = hash_password(long_password)
    assert verify_password(long_password, password_hash) is True


def test_passwords_identical_within_72_bytes_verify_as_equal():
    # Documents bcrypt's real 72-byte limit (not a bug): once truncated,
    # two inputs sharing the first 72 bytes are indistinguishable to bcrypt.
    base = "y" * 72
    password_hash = hash_password(base + "tail-one")
    assert verify_password(base + "tail-two", password_hash) is True


def test_two_hashes_of_same_password_differ():
    # bcrypt salts each hash independently.
    assert hash_password("same-password") != hash_password("same-password")
