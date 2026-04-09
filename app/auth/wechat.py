"""WeChat OAuth 2.0 client for web QR-code login.

Uses stdlib urllib — no external WeChat SDK dependency.
"""

import hashlib
import hmac
import json
import logging
import time
import urllib.parse
import urllib.request

logger = logging.getLogger("signal.auth")

# WeChat API endpoints
AUTHORIZE_URL = "https://open.weixin.qq.com/connect/qrconnect"
ACCESS_TOKEN_URL = "https://api.weixin.qq.com/sns/oauth2/access_token"
USER_INFO_URL = "https://api.weixin.qq.com/sns/userinfo"


def get_authorize_url(app_id, redirect_uri, state):
    """Build the WeChat QR code authorization URL.

    Users are redirected here to scan the QR code with their phone.
    """
    params = urllib.parse.urlencode({
        "appid": app_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": "snsapi_login",
        "state": state,
    })
    return f"{AUTHORIZE_URL}?{params}#wechat_redirect"


def exchange_code_for_token(app_id, app_secret, code):
    """Exchange authorization code for access token.

    Returns dict: {access_token, expires_in, refresh_token, openid, scope, unionid}
    """
    params = urllib.parse.urlencode({
        "appid": app_id,
        "secret": app_secret,
        "code": code,
        "grant_type": "authorization_code",
    })
    url = f"{ACCESS_TOKEN_URL}?{params}"

    with urllib.request.urlopen(url, timeout=10) as resp:
        data = json.loads(resp.read())

    if "errcode" in data and data["errcode"] != 0:
        logger.error("WeChat token exchange failed", extra={
            "event": "wechat_token_error",
            "errcode": data.get("errcode"),
            "errmsg": data.get("errmsg"),
        })
        raise ValueError(f"WeChat API error: {data.get('errmsg', 'unknown')}")

    return data


def fetch_user_info(access_token, openid):
    """Fetch user profile from WeChat.

    Returns dict: {openid, nickname, sex, province, city, country, headimgurl, unionid}
    """
    params = urllib.parse.urlencode({
        "access_token": access_token,
        "openid": openid,
        "lang": "zh_CN",
    })
    url = f"{USER_INFO_URL}?{params}"

    with urllib.request.urlopen(url, timeout=10) as resp:
        data = json.loads(resp.read())

    if "errcode" in data and data["errcode"] != 0:
        logger.error("WeChat user info failed", extra={
            "event": "wechat_userinfo_error",
            "errcode": data.get("errcode"),
            "errmsg": data.get("errmsg"),
        })
        raise ValueError(f"WeChat API error: {data.get('errmsg', 'unknown')}")

    return data


def generate_state(secret, nonce=None):
    """Generate a CSRF-safe state parameter.

    Uses HMAC(timestamp + nonce, secret) so no server-side storage is needed.
    The state encodes the timestamp for expiry validation.
    """
    ts = str(int(time.time()))
    nonce = nonce or hashlib.sha256(ts.encode() + secret.encode()).hexdigest()[:8]
    msg = f"{ts}:{nonce}"
    sig = hmac.new(secret.encode(), msg.encode(), hashlib.sha256).hexdigest()[:16]
    return f"{ts}:{nonce}:{sig}"


def verify_state(state, secret, max_age=300):
    """Verify a state parameter. Returns True if valid and not expired."""
    try:
        parts = state.split(":")
        if len(parts) != 3:
            return False
        ts, nonce, sig = parts
        # Check expiry
        if time.time() - int(ts) > max_age:
            return False
        # Verify HMAC
        msg = f"{ts}:{nonce}"
        expected = hmac.new(secret.encode(), msg.encode(), hashlib.sha256).hexdigest()[:16]
        return hmac.compare_digest(sig, expected)
    except Exception:
        return False
