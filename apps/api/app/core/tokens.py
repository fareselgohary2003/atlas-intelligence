"""Minimal HS256 session tokens (stdlib). Only HS256 is accepted: 'none' and any other algorithm are rejected, signatures are compared in
constant time, and exp/sub/jti are mandatory. A CSRF token is an HMAC bound to the session id (jti)."""
import base64
import hashlib
import hmac
import json
import time
import uuid


class TokenError(Exception):
    pass


def _b64(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def _unb64(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def _sign(msg: bytes, secret: str) -> str:
    return _b64(hmac.new(secret.encode(), msg, hashlib.sha256).digest())


def encode(claims: dict, secret: str) -> str:
    head = _b64(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode())
    body = _b64(json.dumps(claims, separators=(",", ":")).encode())
    return f"{head}.{body}.{_sign(f'{head}.{body}'.encode(), secret)}"


def decode(token: str, secret: str, now: float | None = None) -> dict:
    try:
        head_b, body_b, sig = token.split(".")
        head = json.loads(_unb64(head_b))
        if head.get("alg") != "HS256":
            raise TokenError("unsupported algorithm")
        if not hmac.compare_digest(sig, _sign(f"{head_b}.{body_b}".encode(), secret)):
            raise TokenError("bad signature")
        claims = json.loads(_unb64(body_b))
    except TokenError:
        raise
    except Exception:
        raise TokenError("malformed token")
    exp = claims.get("exp")
    if isinstance(exp, bool) or not isinstance(exp, (int, float)) or exp <= (time.time() if now is None else now):
        raise TokenError("expired or missing exp")
    if not isinstance(claims.get("sub"), str) or not isinstance(claims.get("jti"), str):
        raise TokenError("missing claims")
    return claims


def issue(user_id, secret: str, ttl_seconds: int, now: float | None = None):
    t = time.time() if now is None else now
    jti = uuid.uuid4().hex
    return encode({"sub": str(user_id), "iat": int(t), "exp": int(t) + ttl_seconds, "jti": jti}, secret), jti


def csrf_token(secret: str, jti: str) -> str:
    return hmac.new(secret.encode(), f"csrf:{jti}".encode(), hashlib.sha256).hexdigest()


def verify_csrf(secret: str, jti: str, presented) -> bool:
    return isinstance(presented, str) and bool(presented) and hmac.compare_digest(presented, csrf_token(secret, jti))
