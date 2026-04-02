"""Firebase Admin SDK initialization and token verification."""

import os
import json

_firebase_app = None


def init_firebase():
    """Initialize Firebase Admin SDK. Call once at app startup."""
    global _firebase_app
    if _firebase_app is not None:
        return _firebase_app

    import firebase_admin
    from firebase_admin import credentials

    # Option 1: Service account JSON file path
    cred_path = os.environ.get("FIREBASE_CREDENTIALS")
    # Option 2: Service account JSON as env var (for containers/CI)
    cred_json = os.environ.get("FIREBASE_CREDENTIALS_JSON")

    if cred_path:
        cred = credentials.Certificate(cred_path)
    elif cred_json:
        cred = credentials.Certificate(json.loads(cred_json))
    else:
        # Falls back to Application Default Credentials (GCP environments)
        cred = credentials.ApplicationDefault()

    _firebase_app = firebase_admin.initialize_app(cred)
    return _firebase_app


def verify_id_token(id_token):
    """Verify a Firebase ID token and return the decoded claims.

    Returns decoded token dict with 'uid', 'email', 'name', 'picture', etc.
    Raises ValueError or firebase_admin.auth.InvalidIdTokenError on failure.
    """
    from firebase_admin import auth
    return auth.verify_id_token(id_token)
