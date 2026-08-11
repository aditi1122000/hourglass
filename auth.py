"""Password hashing helpers for Hourglass app-level login."""

from passlib.hash import bcrypt


def hash_password(plain_password):
    return bcrypt.hash(plain_password)


def verify_password(plain_password, password_hash):
    return bcrypt.verify(plain_password, password_hash)
