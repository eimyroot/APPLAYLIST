from dataclasses import dataclass


@dataclass(frozen=True)
class AuthContext:
    subject: str
    role: str
    authenticated: bool = False


def get_anonymous_context() -> AuthContext:
    return AuthContext(subject="anonymous", role="viewer", authenticated=False)
