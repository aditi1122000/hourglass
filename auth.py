"""Password hashing helpers for Hourglass app-level login."""

import bcrypt

# bcrypt only ever looks at the first 72 bytes of a password and raises on
# anything longer -- truncate up front so hash/verify agree on long inputs
# instead of crashing the login form for someone with a long passphrase.
_MAX_PASSWORD_BYTES = 72


def _encode(plain_password):
    return plain_password.encode("utf-8")[:_MAX_PASSWORD_BYTES]


def hash_password(plain_password):
    return bcrypt.hashpw(_encode(plain_password), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password, password_hash):
    return bcrypt.checkpw(_encode(plain_password), password_hash.encode("utf-8"))
