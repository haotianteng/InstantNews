"""SEC EDGAR client — institutional holdings (13F), position changes (13D/13G), insider trades (Form 4).

Provides EdgarClient with three main methods:
- get_institutional_holders(symbol): top institutional holders from 13F filings
- get_major_position_changes(symbol): recent 13D/13G filings
- get_insider_transactions(symbol): recent Form 4 insider transactions

User-Agent set per SEC EDGAR policy. Rate limit: 10 req/sec via throttle.
No API key required — SEC EDGAR is free public data.
"""

import logging
import time
from typing import Any, Optional
from xml.etree import ElementTree

import requests

logger = logging.getLogger("signal.edgar")

EDGAR_BASE_URL = "https://efts.sec.gov/LATEST"
EDGAR_DATA_URL = "https://data.sec.gov"
EDGAR_USER_AGENT = "InstantNews dev@instnews.net"

# Cache TTLs per acceptance criteria
INSTITUTIONAL_TTL = 86400  # 24 hours for 13F
POSITION_CHANGE_TTL = 21600  # 6 hours for 13D/13G
INSIDER_TTL = 3600  # 1 hour for Form 4

# SEC rate limit: 10 req/sec — minimum 0.1s between requests
_MIN_REQUEST_INTERVAL = 0.1


class _CacheEntry:
    __slots__ = ("value", "expires_at")

    def __init__(self, value: Any, ttl: float) -> None:
        self.value = value
        self.expires_at = time.monotonic() + ttl

    def is_valid(self) -> bool:
        return time.monotonic() < self.expires_at


class EdgarClient:
    """Client for SEC EDGAR filings with in-memory caching and rate limiting."""

    def __init__(self) -> None:
        self._session = requests.Session()
        self._session.headers.update({
            "User-Agent": EDGAR_USER_AGENT,
            "Accept-Encoding": "gzip, deflate",
        })
        self._last_request_time = 0.0
        self._cik_cache: dict[str, _CacheEntry] = {}
        self._institutional_cache: dict[str, _CacheEntry] = {}
        self._position_cache: dict[str, _CacheEntry] = {}
        self._insider_cache: dict[str, _CacheEntry] = {}

    @property
    def enabled(self) -> bool:
        return True  # EDGAR is free, always enabled

    def _throttle(self) -> None:
        """Enforce SEC EDGAR 10 req/sec rate limit."""
        now = time.monotonic()
        elapsed = now - self._last_request_time
        if elapsed < _MIN_REQUEST_INTERVAL:
            time.sleep(_MIN_REQUEST_INTERVAL - elapsed)
        self._last_request_time = time.monotonic()

    def _get(self, url: str, params: Optional[dict[str, Any]] = None,
             timeout: int = 15) -> requests.Response:
        """Rate-limited GET request."""
        self._throttle()
        return self._session.get(url, params=params, timeout=timeout)

    def _resolve_cik(self, symbol: str) -> Optional[str]:
        """Resolve ticker symbol to SEC CIK number (zero-padded to 10 digits)."""
        cached = self._cik_cache.get(symbol)
        if cached and cached.is_valid():
            return cached.value

        # Primary: use company tickers JSON for ticker → CIK mapping
        try:
            url = f"{EDGAR_DATA_URL}/files/company_tickers.json"
            resp = self._get(url)
            resp.raise_for_status()
            tickers = resp.json()

            for entry in tickers.values():
                if entry.get("ticker", "").upper() == symbol:
                    cik_padded = str(entry["cik_str"]).zfill(10)
                    self._cik_cache[symbol] = _CacheEntry(cik_padded, 86400)
                    return cik_padded

        except (requests.exceptions.RequestException, ValueError, KeyError) as e:
            logger.warning("edgar: CIK lookup failed for %s: %s", symbol, e)

        return None

    def get_institutional_holders(self, symbol: str, limit: int = 20) -> Optional[list[dict[str, Any]]]:
        """Fetch top institutional holders from latest 13F filings.

        Returns list of holders, each with: institution_name, shares_held, value,
        report_date, change_type.
        """
        symbol = symbol.upper().strip()
        cached = self._institutional_cache.get(symbol)
        if cached and cached.is_valid():
            return cached.value

        try:
            # Use EFTS full-text search to find 13F-HR filings mentioning this ticker
            resp = self._get(
                f"{EDGAR_BASE_URL}/search-index",
                params={
                    "q": f'"{symbol}"',
                    "forms": "13F-HR,13F-HR/A",
                    "from": "0",
                    "size": str(min(limit, 40)),
                },
            )

            holders: list[dict[str, Any]] = []

            if resp.status_code == 200:
                data = resp.json()
                hits = data.get("hits", {}).get("hits", [])

                seen_filers: set[str] = set()
                for hit in hits:
                    source = hit.get("_source", {})
                    display_names = source.get("display_names", [])
                    filer_name = source.get("entity_name", display_names[0] if display_names else "Unknown")
                    filing_date = source.get("file_date", "")

                    if filer_name in seen_filers:
                        continue
                    seen_filers.add(filer_name)

                    holders.append({
                        "institution_name": filer_name,
                        "shares_held": None,
                        "value": None,
                        "report_date": filing_date,
                        "change_type": "held",
                    })

                    if len(holders) >= limit:
                        break

            self._institutional_cache[symbol] = _CacheEntry(holders, INSTITUTIONAL_TTL)
            return holders

        except requests.exceptions.HTTPError as e:
            if e.response is not None and e.response.status_code == 404:
                logger.warning("edgar 13F: ticker %s not found", symbol)
            else:
                logger.warning("edgar 13F: HTTP error for %s: %s", symbol, e)
            return None
        except (requests.exceptions.RequestException, ValueError, KeyError) as e:
            logger.warning("edgar 13F: error fetching %s: %s", symbol, e)
            return None

    def get_major_position_changes(self, symbol: str, limit: int = 10) -> Optional[list[dict[str, Any]]]:
        """Fetch recent 13D/13G filings (major position changes) for a company.

        Returns list of filings, each with: filer_name, filing_date, filing_type,
        percent_owned, shares_held, change_description.
        """
        symbol = symbol.upper().strip()
        cached = self._position_cache.get(symbol)
        if cached and cached.is_valid():
            return cached.value

        try:
            cik = self._resolve_cik(symbol)
            if not cik:
                result: list[dict[str, Any]] = []
                self._position_cache[symbol] = _CacheEntry(result, POSITION_CHANGE_TTL)
                return result

            # Fetch company submissions to find SC 13D and SC 13G filings
            url = f"{EDGAR_DATA_URL}/submissions/CIK{cik}.json"
            resp = self._get(url)
            resp.raise_for_status()
            data = resp.json()

            recent = data.get("filings", {}).get("recent", {})
            forms = recent.get("form", [])
            dates = recent.get("filingDate", [])
            accessions = recent.get("accessionNumber", [])
            primary_docs = recent.get("primaryDocument", [])

            results: list[dict[str, Any]] = []

            for i, form_type in enumerate(forms):
                if form_type not in ("SC 13D", "SC 13D/A", "SC 13G", "SC 13G/A"):
                    continue

                filing_date = dates[i] if i < len(dates) else ""
                accession = accessions[i] if i < len(accessions) else ""
                primary_doc = primary_docs[i] if i < len(primary_docs) else ""

                # Try to extract ownership details from the filing
                percent_owned = None
                shares_held_val = None
                filer_name = "Unknown Filer"

                # Attempt to fetch filing details
                if accession and primary_doc:
                    filer_name, percent_owned, shares_held_val = self._parse_13dg_filing(
                        cik, accession, primary_doc
                    )

                is_amendment = "/A" in form_type
                change_desc = f"{'Amended ' if is_amendment else ''}{'Schedule 13D' if '13D' in form_type else 'Schedule 13G'} filing"

                results.append({
                    "filer_name": filer_name,
                    "filing_date": filing_date,
                    "filing_type": form_type,
                    "percent_owned": percent_owned,
                    "shares_held": shares_held_val,
                    "change_description": change_desc,
                })

                if len(results) >= limit:
                    break

            self._position_cache[symbol] = _CacheEntry(results, POSITION_CHANGE_TTL)
            return results

        except requests.exceptions.HTTPError as e:
            if e.response is not None and e.response.status_code == 404:
                logger.warning("edgar 13D/G: ticker %s not found", symbol)
            else:
                logger.warning("edgar 13D/G: HTTP error for %s: %s", symbol, e)
            return None
        except (requests.exceptions.RequestException, ValueError, KeyError) as e:
            logger.warning("edgar 13D/G: error fetching %s: %s", symbol, e)
            return None

    def _parse_13dg_filing(self, cik: str, accession: str, primary_doc: str) -> tuple[str, Optional[float], Optional[int]]:
        """Try to extract filer name and ownership from a 13D/13G filing."""
        filer_name = "Unknown Filer"
        percent_owned: Optional[float] = None
        shares_held: Optional[int] = None

        try:
            # Fetch the filing index to get filer info
            acc_no_dashes = accession.replace("-", "")
            index_url = f"{EDGAR_DATA_URL}/Archives/edgar/data/{cik}/{acc_no_dashes}/{accession}-index.htm"
            resp = self._get(index_url)
            if resp.status_code == 200:
                text = resp.text
                # Try to extract filer name from filing header
                if "COMPANY CONFORMED NAME:" in text:
                    start = text.index("COMPANY CONFORMED NAME:") + len("COMPANY CONFORMED NAME:")
                    end = text.index("\n", start) if "\n" in text[start:start+200] else start + 100
                    filer_name = text[start:end].strip()[:100]
        except (requests.exceptions.RequestException, ValueError):
            pass

        return filer_name, percent_owned, shares_held

    def get_insider_transactions(self, symbol: str, limit: int = 20) -> Optional[list[dict[str, Any]]]:
        """Fetch recent Form 4 insider transactions for a company.

        Returns list of transactions, each with: filing_date, insider_name, title,
        transaction_type, shares, price_per_share, total_value, shares_held_after.
        """
        symbol = symbol.upper().strip()
        cached = self._insider_cache.get(symbol)
        if cached and cached.is_valid():
            return cached.value

        try:
            cik = self._resolve_cik(symbol)
            if not cik:
                result: list[dict[str, Any]] = []
                self._insider_cache[symbol] = _CacheEntry(result, INSIDER_TTL)
                return result

            # Fetch company submissions to find Form 4 filings
            url = f"{EDGAR_DATA_URL}/submissions/CIK{cik}.json"
            resp = self._get(url)
            resp.raise_for_status()
            data = resp.json()

            recent = data.get("filings", {}).get("recent", {})
            forms = recent.get("form", [])
            dates = recent.get("filingDate", [])
            accessions = recent.get("accessionNumber", [])
            primary_docs = recent.get("primaryDocument", [])

            results: list[dict[str, Any]] = []

            for i, form_type in enumerate(forms):
                if form_type not in ("4", "4/A"):
                    continue

                filing_date = dates[i] if i < len(dates) else ""
                accession = accessions[i] if i < len(accessions) else ""
                primary_doc = primary_docs[i] if i < len(primary_docs) else ""

                # Parse the Form 4 XML for transaction details
                transactions = self._parse_form4_xml(cik, accession, primary_doc)
                for txn in transactions:
                    txn["filing_date"] = filing_date
                    results.append(txn)

                    if len(results) >= limit:
                        break

                if len(results) >= limit:
                    break

            self._insider_cache[symbol] = _CacheEntry(results, INSIDER_TTL)
            return results

        except requests.exceptions.HTTPError as e:
            if e.response is not None and e.response.status_code == 404:
                logger.warning("edgar form4: ticker %s not found", symbol)
            else:
                logger.warning("edgar form4: HTTP error for %s: %s", symbol, e)
            return None
        except (requests.exceptions.RequestException, ValueError, KeyError) as e:
            logger.warning("edgar form4: error fetching %s: %s", symbol, e)
            return None

    def _parse_form4_xml(self, cik: str, accession: str, primary_doc: str) -> list[dict[str, Any]]:
        """Parse a Form 4 XML document for insider transaction details."""
        transactions: list[dict[str, Any]] = []

        if not accession or not primary_doc:
            return transactions

        try:
            acc_no_dashes = accession.replace("-", "")
            doc_url = f"{EDGAR_DATA_URL}/Archives/edgar/data/{cik}/{acc_no_dashes}/{primary_doc}"
            resp = self._get(doc_url)

            if resp.status_code != 200:
                return transactions

            # Form 4 filings are XML
            if not primary_doc.endswith(".xml"):
                return transactions

            root = ElementTree.fromstring(resp.content)

            # Extract reporting owner info
            owner_el = root.find(".//reportingOwner")
            insider_name = ""
            title = ""
            if owner_el is not None:
                owner_id = owner_el.find("reportingOwnerId")
                if owner_id is not None:
                    name_el = owner_id.find("rptOwnerName")
                    insider_name = name_el.text.strip() if name_el is not None and name_el.text else ""

                relationship = owner_el.find("reportingOwnerRelationship")
                if relationship is not None:
                    title_el = relationship.find("officerTitle")
                    if title_el is not None and title_el.text:
                        title = title_el.text.strip()
                    elif relationship.find("isDirector") is not None:
                        is_dir = relationship.find("isDirector")
                        if is_dir is not None and is_dir.text and is_dir.text.strip() in ("1", "true"):
                            title = "Director"

            # Extract non-derivative transactions
            for txn_el in root.findall(".//nonDerivativeTransaction"):
                txn = self._extract_transaction(txn_el, insider_name, title)
                if txn:
                    transactions.append(txn)

            # Also check derivative transactions
            for txn_el in root.findall(".//derivativeTransaction"):
                txn = self._extract_transaction(txn_el, insider_name, title)
                if txn:
                    txn["transaction_type"] = f"Derivative {txn.get('transaction_type', '')}"
                    transactions.append(txn)

        except (ElementTree.ParseError, requests.exceptions.RequestException) as e:
            logger.warning("edgar form4 XML parse: error for %s/%s: %s", cik, accession, e)

        return transactions

    def _extract_transaction(self, txn_el: ElementTree.Element, insider_name: str, title: str) -> Optional[dict[str, Any]]:
        """Extract transaction details from a Form 4 XML transaction element."""
        coding = txn_el.find(".//transactionCoding")
        if coding is None:
            return None

        code_el = coding.find("transactionCode")
        tx_code = code_el.text.strip() if code_el is not None and code_el.text else ""

        # Map transaction codes to readable types
        code_map = {
            "P": "Purchase",
            "S": "Sale",
            "A": "Grant/Award",
            "D": "Disposition (non-open market)",
            "F": "Tax withholding",
            "M": "Option exercise",
            "G": "Gift",
            "C": "Conversion",
            "X": "Option expiration",
            "J": "Other",
        }
        transaction_type = code_map.get(tx_code, tx_code)

        # Extract amounts
        amounts = txn_el.find(".//transactionAmounts")
        shares: Optional[float] = None
        price_per_share: Optional[float] = None

        if amounts is not None:
            shares_el = amounts.find("transactionShares/value")
            if shares_el is not None and shares_el.text:
                try:
                    shares = float(shares_el.text.strip())
                except ValueError:
                    pass

            price_el = amounts.find("transactionPricePerShare/value")
            if price_el is not None and price_el.text:
                try:
                    price_per_share = float(price_el.text.strip())
                except ValueError:
                    pass

        total_value: Optional[float] = None
        if shares is not None and price_per_share is not None:
            total_value = round(shares * price_per_share, 2)

        # Shares held after
        post_el = txn_el.find(".//postTransactionAmounts/sharesOwnedFollowingTransaction/value")
        shares_held_after: Optional[float] = None
        if post_el is not None and post_el.text:
            try:
                shares_held_after = float(post_el.text.strip())
            except ValueError:
                pass

        return {
            "filing_date": "",  # Set by caller
            "insider_name": insider_name,
            "title": title,
            "transaction_type": transaction_type,
            "shares": shares,
            "price_per_share": price_per_share,
            "total_value": total_value,
            "shares_held_after": shares_held_after,
        }
