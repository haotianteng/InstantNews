"""Diplomatic social-media watchlist — foreign ministers and MFAs.

Edit this list to add/remove accounts. Handles are case-insensitive on X; we store
them in the canonical casing shown here. `country_code` uses ISO 3166-1 alpha-2.

For Trump, we use Truth Social via CNN's mirror (no X handle needed).
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class DiplomaticHandle:
    handle: str          # without leading '@'
    country_code: str    # ISO 3166-1 alpha-2, or 'EU', 'UN', 'NATO'
    role: str            # FM / MFA / Spokesperson / HighRep / SecGen
    platform: str        # 'twitter' or 'truth_social'
    display_name: str    # human-readable


# 24 Twitter + 1 Truth Social = 25 total. Update handles when ministers change.
# Sources are chosen for activity + availability (some ministers don't have
# personal accounts; we use the MFA's English account instead).
DIPLOMATIC_ACCOUNTS: list[DiplomaticHandle] = [
    # Core G7 + China/Russia/Iran/Israel
    DiplomaticHandle("SecRubio",         "US", "FM",  "twitter", "Marco Rubio (US Secretary of State)"),
    DiplomaticHandle("DavidLammy",       "GB", "FM",  "twitter", "David Lammy (UK Foreign Secretary)"),
    DiplomaticHandle("ABaerbock",        "DE", "FM",  "twitter", "Annalena Baerbock (Germany FM)"),
    DiplomaticHandle("francediplo_EN",   "FR", "MFA", "twitter", "France MFA (English)"),
    DiplomaticHandle("ItalyMFA",         "IT", "MFA", "twitter", "Italy MFA"),
    DiplomaticHandle("MofaJapan_en",     "JP", "MFA", "twitter", "Japan MFA (English)"),
    DiplomaticHandle("MelanieJoly",      "CA", "FM",  "twitter", "Melanie Joly (Canada FM)"),
    DiplomaticHandle("SpokespersonCHN",  "CN", "Spokesperson", "twitter", "China MFA Spokesperson"),
    DiplomaticHandle("mfa_russia",       "RU", "MFA", "twitter", "Russia MFA"),
    DiplomaticHandle("araghchi",         "IR", "FM",  "twitter", "Abbas Araghchi (Iran FM)"),
    DiplomaticHandle("gidonsaar",        "IL", "FM",  "twitter", "Gideon Sa'ar (Israel FM)"),

    # Expanded set — major regional powers
    DiplomaticHandle("DrSJaishankar",    "IN", "FM",  "twitter", "S. Jaishankar (India FM)"),
    DiplomaticHandle("MOFAkr_eng",       "KR", "MFA", "twitter", "South Korea MFA (English)"),
    DiplomaticHandle("KSAmofaEN",        "SA", "MFA", "twitter", "Saudi Arabia MFA (English)"),
    DiplomaticHandle("HakanFidan",       "TR", "FM",  "twitter", "Hakan Fidan (Türkiye FM)"),
    DiplomaticHandle("ABZayed",          "AE", "FM",  "twitter", "Abdullah bin Zayed (UAE FM)"),
    DiplomaticHandle("MfaEgypt",         "EG", "MFA", "twitter", "Egypt MFA"),
    DiplomaticHandle("SybihaAndrii",     "UA", "FM",  "twitter", "Andrii Sybiha (Ukraine FM)"),
    DiplomaticHandle("ItamaratyGovBr",   "BR", "MFA", "twitter", "Brazil MFA"),
    DiplomaticHandle("SRE_mx",           "MX", "MFA", "twitter", "Mexico MFA"),
    DiplomaticHandle("SenatorWong",      "AU", "FM",  "twitter", "Penny Wong (Australia FM)"),

    # Supranational
    DiplomaticHandle("kajakallas",       "EU",   "HighRep", "twitter", "Kaja Kallas (EU High Rep for Foreign Policy)"),
    DiplomaticHandle("SecGenNATO",       "NATO", "SecGen",  "twitter", "NATO Secretary General"),
    DiplomaticHandle("antonioguterres",  "UN",   "SecGen",  "twitter", "António Guterres (UN SecGen)"),

    # Trump — via Truth Social (CNN mirror, no X API)
    DiplomaticHandle("realDonaldTrump",  "US", "President", "truth_social", "Donald J. Trump (US President)"),
]


def twitter_handles() -> list[str]:
    """Just the @handles for Twitter accounts (no prefix)."""
    return [a.handle for a in DIPLOMATIC_ACCOUNTS if a.platform == "twitter"]


def truth_social_handles() -> list[str]:
    """Truth Social handles (for filtering the CNN mirror if it ever adds more authors)."""
    return [a.handle for a in DIPLOMATIC_ACCOUNTS if a.platform == "truth_social"]


def handle_metadata(handle: str) -> DiplomaticHandle | None:
    """Look up metadata by @handle (case-insensitive)."""
    lower = handle.lower()
    for a in DIPLOMATIC_ACCOUNTS:
        if a.handle.lower() == lower:
            return a
    return None
