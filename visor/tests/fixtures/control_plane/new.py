"""Fixture corregida: un token revocado nunca autoriza."""


def authorize(revoked):
    return not revoked
