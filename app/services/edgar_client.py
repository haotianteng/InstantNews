"""SEC EDGAR client — institutional holdings (13F), position changes (13D/13G), insider trades (Form 4).

Provides EdgarClient with three main methods:
- get_institutional_holders(symbol): top institutional holders from 13F filings
- get_major_position_changes(symbol): recent 13D/13G filings
- get_insider_transactions(symbol): recent Form 4 insider transactions

User-Agent set per SEC EDGAR policy. Rate limit: 10 req/sec via throttle.
No API key required — SEC EDGAR is free public data.
"""

import logging
import re
import time
from datetime import datetime, timedelta
from typing import Any, Optional
from xml.etree import ElementTree

import requests

logger = logging.getLogger("signal.edgar")

EDGAR_BASE_URL = "https://efts.sec.gov/LATEST"
EDGAR_DATA_URL = "https://data.sec.gov"
EDGAR_SEC_URL = "https://www.sec.gov"
EDGAR_USER_AGENT = "InstantNews dev@instnews.net"

_13F_NS = "http://www.sec.gov/edgar/document/thirteenf/informationtable"

# Cache TTLs per acceptance criteria
INSTITUTIONAL_TTL = 86400  # 24 hours for 13F
POSITION_CHANGE_TTL = 21600  # 6 hours for 13D/13G
INSIDER_TTL = 3600  # 1 hour for Form 4

# SEC rate limit: 10 req/sec — minimum 0.1s between requests
_MIN_REQUEST_INTERVAL = 0.1


def _normalize_company_name(name: str) -> str:
    """Normalize a company name for matching by removing common suffixes and punctuation."""
    n = name.upper().replace(".", "").replace(",", "").strip()
    for suffix in (" INC", " CORP", " CORPORATION", " CO", " LTD", " LLC", " LP", " PLC", " GROUP"):
        if n.endswith(suffix):
            n = n[: -len(suffix)].strip()
    return n


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
        self._company_names: dict[str, str] = {}  # symbol → company title
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
            url = f"{EDGAR_SEC_URL}/files/company_tickers.json"
            resp = self._get(url)
            resp.raise_for_status()
            tickers = resp.json()

            for entry in tickers.values():
                if entry.get("ticker", "").upper() == symbol:
                    cik_padded = str(entry["cik_str"]).zfill(10)
                    self._cik_cache[symbol] = _CacheEntry(cik_padded, 86400)
                    self._company_names[symbol] = entry.get("title", "")
                    return cik_padded

        except (requests.exceptions.RequestException, ValueError, KeyError) as e:
            logger.warning("edgar: CIK lookup failed for %s: %s", symbol, e)

        return None

    def get_institutional_holders(self, symbol: str, limit: int = 20) -> Optional[list[dict[str, Any]]]:
        """Fetch top institutional holders from latest 13F filings.

        Searches EFTS for 13F information tables mentioning the company, then
        parses each filing's XML to extract real shares_held and value data.

        Returns list of holders, each with: institution_name, shares_held, value,
        report_date, change_type.
        """
        symbol = symbol.upper().strip()
        cached = self._institutional_cache.get(symbol)
        if cached and cached.is_valid():
            return cached.value

        try:
            # Resolve company name for searching 13F info tables
            self._resolve_cik(symbol)
            company_name = self._company_names.get(symbol, symbol)
            search_term = _normalize_company_name(company_name) or symbol

            # Date window: last 18 months to get recent filings
            end_dt = datetime.now()
            start_dt = end_dt - timedelta(days=540)

            resp = self._get(
                f"{EDGAR_BASE_URL}/search-index",
                params={
                    "q": f'"{search_term}"',
                    "forms": "13F-HR,13F-HR/A",
                    "dateRange": "custom",
                    "startdt": start_dt.strftime("%Y-%m-%d"),
                    "enddt": end_dt.strftime("%Y-%m-%d"),
                    "from": "0",
                    "size": str(min(limit * 3, 60)),
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
                    raw_name = display_names[0] if display_names else "Unknown"
                    # Strip " (CIK ...)" suffix from display name
                    filer_name = raw_name.split("(CIK")[0].strip() if "(CIK" in raw_name else raw_name

                    if filer_name in seen_filers:
                        continue
                    seen_filers.add(filer_name)

                    period = source.get("period_ending", source.get("file_date", ""))
                    ciks = source.get("ciks", [])
                    adsh = source.get("adsh", "")
                    _id = hit.get("_id", "")
                    filename = _id.split(":", 1)[1] if ":" in _id else ""

                    # Fetch and parse the 13F info table for this filer
                    shares_held, value = self._parse_13f_for_company(
                        ciks[0] if ciks else "", adsh, filename,
                        company_name, symbol,
                    )

                    holders.append({
                        "institution_name": filer_name,
                        "shares_held": shares_held,
                        "value": value,
                        "report_date": period,
                        "change_type": "held",
                    })

                    if len(holders) >= limit:
                        break

            # Sort by value descending (entries with data first, then nulls)
            holders.sort(key=lambda h: h["value"] or 0, reverse=True)

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

    def _parse_13f_for_company(
        self, cik: str, adsh: str, filename: str,
        company_name: str, ticker: str,
    ) -> tuple[Optional[int], Optional[int]]:
        """Fetch a 13F information table and extract shares/value for the target company."""
        if not cik or not adsh or not filename:
            return None, None

        try:
            cik_int = str(int(cik))
            adsh_nodash = adsh.replace("-", "")
            url = f"{EDGAR_SEC_URL}/Archives/edgar/data/{cik_int}/{adsh_nodash}/{filename}"
            resp = self._get(url, timeout=20)

            if resp.status_code != 200:
                return None, None

            root = ElementTree.fromstring(resp.content)
            name_core = _normalize_company_name(company_name)
            ticker_upper = ticker.upper()

            # Find all infoTable entries (handle namespace variants)
            entries = root.findall(f".//{{{_13F_NS}}}infoTable")
            if not entries:
                entries = root.findall(".//infoTable")

            total_shares = 0
            total_value = 0
            found = False

            for entry in entries:
                issuer_el = entry.find(f"{{{_13F_NS}}}nameOfIssuer")
                if issuer_el is None:
                    issuer_el = entry.find("nameOfIssuer")
                if issuer_el is None or issuer_el.text is None:
                    continue

                issuer_name = issuer_el.text.strip().upper()
                issuer_core = _normalize_company_name(issuer_name)

                # Match by normalized company name (equality) or exact ticker
                if not (issuer_core == name_core or issuer_name == ticker_upper):
                    continue

                found = True

                # Value in dollars (as reported in 13F XML)
                val_el = entry.find(f"{{{_13F_NS}}}value")
                if val_el is None:
                    val_el = entry.find("value")
                if val_el is not None and val_el.text:
                    try:
                        total_value += int(val_el.text.strip())
                    except ValueError:
                        pass

                # Shares held
                shr_el = entry.find(f".//{{{_13F_NS}}}sshPrnamt")
                if shr_el is None:
                    shr_el = entry.find(".//sshPrnamt")
                if shr_el is not None and shr_el.text:
                    try:
                        total_shares += int(shr_el.text.strip())
                    except ValueError:
                        pass

            if found:
                return total_shares or None, total_value or None
            return None, None

        except (ElementTree.ParseError, requests.exceptions.RequestException,
                ValueError, KeyError) as e:
            logger.warning("edgar 13F XML parse: %s/%s: %s", cik, adsh, e)
            return None, None

    def get_major_position_changes(self, symbol: str, limit: int = 10) -> Optional[list[dict[str, Any]]]:
        """Fetch recent 13D/13G filings (major position changes) for a company.

        Uses EFTS full-text search to find SC 13D/13G filings mentioning the
        company, extracting filer names from search results and ownership data
        from the filing documents.

        Returns list of filings, each with: filer_name, filing_date, filing_type,
        percent_owned, shares_held, change_description.
        """
        symbol = symbol.upper().strip()
        cached = self._position_cache.get(symbol)
        if cached and cached.is_valid():
            return cached.value

        try:
            # Resolve CIK and company name for search filtering
            target_cik = self._resolve_cik(symbol)
            company_name = self._company_names.get(symbol, symbol)
            search_term = _normalize_company_name(company_name) or symbol

            end_dt = datetime.now()
            start_dt = end_dt - timedelta(days=1095)

            resp = self._get(
                f"{EDGAR_BASE_URL}/search-index",
                params={
                    "q": f'"{search_term}"',
                    "forms": "SC 13D,SC 13D/A,SC 13G,SC 13G/A",
                    "dateRange": "custom",
                    "startdt": start_dt.strftime("%Y-%m-%d"),
                    "enddt": end_dt.strftime("%Y-%m-%d"),
                    "from": "0",
                    "size": str(min(limit * 5, 50)),
                },
            )

            results: list[dict[str, Any]] = []

            if resp.status_code == 200:
                data = resp.json()
                hits = data.get("hits", {}).get("hits", [])

                seen_filers: set[str] = set()
                for hit in hits:
                    source = hit.get("_source", {})
                    ciks = source.get("ciks", [])
                    display_names = source.get("display_names", [])

                    # Filter: subject company CIK must match our target
                    if target_cik and ciks and ciks[0] != target_cik:
                        continue

                    # Filer name is the second display_name (subject company is first)
                    if len(display_names) >= 2:
                        raw_filer = display_names[1]
                    elif display_names:
                        raw_filer = display_names[0]
                    else:
                        continue

                    # Clean: strip "(CIK ...)" and ticker symbol parentheticals
                    filer_name = raw_filer.split("(CIK")[0].strip()
                    filer_name = re.sub(r"\s*\([A-Z0-9, -]+\)\s*$", "", filer_name).strip()

                    if not filer_name or filer_name in seen_filers:
                        continue
                    seen_filers.add(filer_name)

                    filing_date = source.get("file_date", "")
                    form_type = source.get("form", "") or source.get("file_type", "") or "SC 13G"
                    adsh = source.get("adsh", "")
                    _id = hit.get("_id", "")
                    filename = _id.split(":", 1)[1] if ":" in _id else ""

                    # Try to fetch ownership data from the filing document
                    percent_owned = None
                    shares_held_val = None
                    filer_cik = ciks[1] if len(ciks) >= 2 else ""
                    if filer_cik and adsh and filename:
                        percent_owned, shares_held_val = self._parse_13dg_ownership(
                            filer_cik, adsh, filename
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

    def _parse_13dg_ownership(
        self, filer_cik: str, adsh: str, filename: str,
    ) -> tuple[Optional[float], Optional[int]]:
        """Fetch a 13D/13G filing document and extract percent_owned and shares_held."""
        percent_owned: Optional[float] = None
        shares_held: Optional[int] = None

        try:
            cik_int = str(int(filer_cik))
            adsh_nodash = adsh.replace("-", "")
            url = f"{EDGAR_SEC_URL}/Archives/edgar/data/{cik_int}/{adsh_nodash}/{filename}"
            resp = self._get(url, timeout=15)

            if resp.status_code != 200:
                return None, None

            # Strip HTML tags for text-based parsing
            text = re.sub(r"<[^>]+>", "\n", resp.text)
            text = re.sub(r"&\w+;", " ", text)
            lines = [line.strip() for line in text.split("\n") if line.strip()]

            for i, line in enumerate(lines):
                # Item 9: AGGREGATE AMOUNT BENEFICIALLY OWNED
                if shares_held is None and re.search(
                    r"AGGREGATE\s+AMOUNT\s+BENEFICIALLY\s+OWNED", line, re.I,
                ):
                    for j in range(i + 1, min(i + 5, len(lines))):
                        m = re.search(r"^([\d,]+)$", lines[j])
                        if m:
                            try:
                                shares_held = int(m.group(1).replace(",", ""))
                            except ValueError:
                                pass
                            break

                # Item 11: PERCENT OF CLASS
                if percent_owned is None and re.search(
                    r"PERCENT\s+OF\s+CLASS", line, re.I,
                ):
                    for j in range(i + 1, min(i + 5, len(lines))):
                        m = re.search(r"([\d.]+)\s*%", lines[j])
                        if m:
                            try:
                                percent_owned = float(m.group(1))
                            except ValueError:
                                pass
                            break

            if shares_held is not None or percent_owned is not None:
                return percent_owned, shares_held

        except (requests.exceptions.RequestException, ValueError) as e:
            logger.warning("edgar 13D/G parse: %s/%s: %s", filer_cik, adsh, e)

        return percent_owned, shares_held

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
            # Strip XSL transformation prefix (e.g. "xslF345X06/form4.xml" → "form4.xml")
            clean_doc = primary_doc.rsplit("/", 1)[-1] if "/" in primary_doc else primary_doc
            doc_url = f"{EDGAR_SEC_URL}/Archives/edgar/data/{cik}/{acc_no_dashes}/{clean_doc}"
            resp = self._get(doc_url)

            if resp.status_code != 200:
                return transactions

            # Form 4 filings are XML
            if not clean_doc.endswith(".xml"):
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
