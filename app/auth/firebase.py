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
    """Verify a Firebase ID token and return the decoded claims."""
    from firebase_admin import auth
    return auth.verify_id_token(id_token)


def create_firebase_user(email, password, display_name=None):
    """Create a new Firebase user with email/password.

    Returns the UserRecord with .uid, .email, etc.
    Raises firebase_admin.auth.EmailAlreadyExistsError if email is taken.
    """
    from firebase_admin import auth
    kwargs = {"email": email, "password": password, "email_verified": False}
    if display_name:
        kwargs["display_name"] = display_name
    return auth.create_user(**kwargs)


def delete_firebase_user(uid):
    """Delete a Firebase user by UID.

    Silently succeeds if user doesn't exist in Firebase.
    """
    from firebase_admin import auth
    try:
        auth.delete_user(uid)
    except auth.UserNotFoundError:
        pass  # Already deleted or was never a real Firebase user


def get_firebase_user(uid):
    """Get Firebase user by UID. Returns None if not found."""
    from firebase_admin import auth
    try:
        return auth.get_user(uid)
    except auth.UserNotFoundError:
        return None


def get_firebase_user_by_email(email):
    """Get Firebase user by email. Returns None if not found."""
    from firebase_admin import auth
    try:
        return auth.get_user_by_email(email)
    except auth.UserNotFoundError:
        return None
