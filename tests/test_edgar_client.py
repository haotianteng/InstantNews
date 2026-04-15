"""Tests for SEC EDGAR client — 13F, 13D/13G, Form 4 parsers."""

from unittest.mock import MagicMock, patch

from app.services.edgar_client import EdgarClient


# Sample Form 4 XML for testing
SAMPLE_FORM4_XML = b"""<?xml version="1.0"?>
<ownershipDocument>
  <reportingOwner>
    <reportingOwnerId>
      <rptOwnerName>DOE JOHN</rptOwnerName>
    </reportingOwnerId>
    <reportingOwnerRelationship>
      <officerTitle>CEO</officerTitle>
    </reportingOwnerRelationship>
  </reportingOwner>
  <nonDerivativeTable>
    <nonDerivativeTransaction>
      <transactionCoding>
        <transactionCode>P</transactionCode>
      </transactionCoding>
      <transactionAmounts>
        <transactionShares>
          <value>1000</value>
        </transactionShares>
        <transactionPricePerShare>
          <value>150.50</value>
        </transactionPricePerShare>
      </transactionAmounts>
      <postTransactionAmounts>
        <sharesOwnedFollowingTransaction>
          <value>5000</value>
        </sharesOwnedFollowingTransaction>
      </postTransactionAmounts>
    </nonDerivativeTransaction>
  </nonDerivativeTable>
</ownershipDocument>"""


class TestEdgarClientBasic:
    """Basic EdgarClient tests."""

    def test_always_enabled(self):
        client = EdgarClient()
        assert client.enabled is True

    def test_import_works(self):
        from app.services.edgar_client import EdgarClient
        assert EdgarClient is not None


class TestEdgarClientCIKLookup:
    """Tests for CIK resolution."""

    @patch("app.services.edgar_client.requests.Session.get")
    def test_resolve_cik_success(self, mock_get: MagicMock):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {
            "0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."}
        }
        mock_get.return_value = mock_resp

        client = EdgarClient()
        cik = client._resolve_cik("AAPL")
        assert cik == "0000320193"

    @patch("app.services.edgar_client.requests.Session.get")
    def test_resolve_cik_not_found(self, mock_get: MagicMock):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {
            "0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."}
        }
        mock_get.return_value = mock_resp

        client = EdgarClient()
        cik = client._resolve_cik("ZZZZZ")
        assert cik is None

    @patch("app.services.edgar_client.requests.Session.get")
    def test_resolve_cik_cached(self, mock_get: MagicMock):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {
            "0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."}
        }
        mock_get.return_value = mock_resp

        client = EdgarClient()
        client._resolve_cik("AAPL")
        client._resolve_cik("AAPL")
        # Only one request for the CIK lookup (cached)
        assert mock_get.call_count == 1


class TestEdgarClientForm4:
    """Tests for Form 4 parsing."""

    @patch("app.services.edgar_client.requests.Session.get")
    def test_insider_transactions_success(self, mock_get: MagicMock):
        # CIK lookup response
        mock_cik_resp = MagicMock()
        mock_cik_resp.status_code = 200
        mock_cik_resp.raise_for_status = MagicMock()
        mock_cik_resp.json.return_value = {
            "0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."}
        }

        # Submissions response with Form 4 filings
        mock_submissions_resp = MagicMock()
        mock_submissions_resp.status_code = 200
        mock_submissions_resp.raise_for_status = MagicMock()
        mock_submissions_resp.json.return_value = {
            "filings": {
                "recent": {
                    "form": ["4", "10-Q", "4"],
                    "filingDate": ["2025-01-15", "2025-01-10", "2025-01-05"],
                    "accessionNumber": ["0001-23-456789", "0002-23-456789", "0003-23-456789"],
                    "primaryDocument": ["form4.xml", "10q.htm", "form4.xml"],
                }
            }
        }

        # Form 4 XML response
        mock_xml_resp = MagicMock()
        mock_xml_resp.status_code = 200
        mock_xml_resp.content = SAMPLE_FORM4_XML

        mock_get.side_effect = [mock_cik_resp, mock_submissions_resp, mock_xml_resp, mock_xml_resp]

        client = EdgarClient()
        result = client.get_insider_transactions("AAPL")

        assert result is not None
        assert isinstance(result, list)
        assert len(result) > 0

        txn = result[0]
        assert txn["insider_name"] == "DOE JOHN"
        assert txn["title"] == "CEO"
        assert txn["transaction_type"] == "Purchase"
        assert txn["shares"] == 1000.0
        assert txn["price_per_share"] == 150.50
        assert txn["total_value"] == 150500.0
        assert txn["shares_held_after"] == 5000.0

    @patch("app.services.edgar_client.requests.Session.get")
    def test_insider_transactions_caching(self, mock_get: MagicMock):
        mock_cik_resp = MagicMock()
        mock_cik_resp.status_code = 200
        mock_cik_resp.raise_for_status = MagicMock()
        mock_cik_resp.json.return_value = {
            "0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."}
        }

        mock_submissions_resp = MagicMock()
        mock_submissions_resp.status_code = 200
        mock_submissions_resp.raise_for_status = MagicMock()
        mock_submissions_resp.json.return_value = {
            "filings": {"recent": {"form": [], "filingDate": [], "accessionNumber": [], "primaryDocument": []}}
        }

        mock_get.side_effect = [mock_cik_resp, mock_submissions_resp]

        client = EdgarClient()
        result1 = client.get_insider_transactions("AAPL")
        result2 = client.get_insider_transactions("AAPL")

        assert result1 == result2
        # Second call should hit cache, so only 2 HTTP requests total
        assert mock_get.call_count == 2

    @patch("app.services.edgar_client.requests.Session.get")
    def test_insider_transactions_no_cik(self, mock_get: MagicMock):
        # CIK lookup returns empty — ticker not in company_tickers.json
        mock_tickers = MagicMock()
        mock_tickers.status_code = 200
        mock_tickers.raise_for_status = MagicMock()
        mock_tickers.json.return_value = {}

        mock_get.return_value = mock_tickers

        client = EdgarClient()
        result = client.get_insider_transactions("INVALID")
        assert result is not None
        assert result == []


class TestEdgarClient13DG:
    """Tests for 13D/13G position changes."""

    @patch("app.services.edgar_client.requests.Session.get")
    def test_major_position_changes_success(self, mock_get: MagicMock):
        mock_cik_resp = MagicMock()
        mock_cik_resp.status_code = 200
        mock_cik_resp.raise_for_status = MagicMock()
        mock_cik_resp.json.return_value = {
            "0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."}
        }

        mock_submissions_resp = MagicMock()
        mock_submissions_resp.status_code = 200
        mock_submissions_resp.raise_for_status = MagicMock()
        mock_submissions_resp.json.return_value = {
            "filings": {
                "recent": {
                    "form": ["SC 13G", "10-K", "SC 13D/A"],
                    "filingDate": ["2025-02-14", "2025-01-28", "2025-01-10"],
                    "accessionNumber": ["0001-25-000001", "0002-25-000002", "0003-25-000003"],
                    "primaryDocument": ["sc13g.htm", "10k.htm", "sc13da.htm"],
                }
            }
        }

        # Filing index response for 13D/G
        mock_index_resp = MagicMock()
        mock_index_resp.status_code = 200
        mock_index_resp.text = "COMPANY CONFORMED NAME:			VANGUARD GROUP\nSomething else"

        mock_get.side_effect = [mock_cik_resp, mock_submissions_resp, mock_index_resp, mock_index_resp]

        client = EdgarClient()
        result = client.get_major_position_changes("AAPL")

        assert result is not None
        assert isinstance(result, list)
        assert len(result) == 2  # SC 13G and SC 13D/A, not 10-K

        assert result[0]["filing_type"] == "SC 13G"
        assert result[0]["filing_date"] == "2025-02-14"
        assert "13G" in result[0]["change_description"]

        assert result[1]["filing_type"] == "SC 13D/A"
        assert "Amended" in result[1]["change_description"]

    @patch("app.services.edgar_client.requests.Session.get")
    def test_major_position_changes_empty(self, mock_get: MagicMock):
        mock_cik_resp = MagicMock()
        mock_cik_resp.status_code = 200
        mock_cik_resp.raise_for_status = MagicMock()
        mock_cik_resp.json.return_value = {
            "0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."}
        }

        mock_submissions_resp = MagicMock()
        mock_submissions_resp.status_code = 200
        mock_submissions_resp.raise_for_status = MagicMock()
        mock_submissions_resp.json.return_value = {
            "filings": {"recent": {"form": ["10-K", "10-Q"], "filingDate": ["2025-01-28", "2025-01-10"], "accessionNumber": ["a", "b"], "primaryDocument": ["a.htm", "b.htm"]}}
        }

        mock_get.side_effect = [mock_cik_resp, mock_submissions_resp]

        client = EdgarClient()
        result = client.get_major_position_changes("AAPL")
        assert result == []


class TestEdgarClient13F:
    """Tests for 13F institutional holders."""

    @patch("app.services.edgar_client.requests.Session.get")
    def test_institutional_holders_returns_list(self, mock_get: MagicMock):
        # EFTS search response — single request
        mock_search_resp = MagicMock()
        mock_search_resp.status_code = 200
        mock_search_resp.json.return_value = {
            "hits": {
                "hits": [
                    {"_source": {"entity_name": "VANGUARD GROUP", "file_date": "2025-02-14"}},
                    {"_source": {"entity_name": "BLACKROCK INC", "file_date": "2025-02-10"}},
                ]
            }
        }

        mock_get.return_value = mock_search_resp

        client = EdgarClient()
        result = client.get_institutional_holders("AAPL")

        assert result is not None
        assert isinstance(result, list)
        assert len(result) == 2
        assert result[0]["institution_name"] == "VANGUARD GROUP"
        assert result[1]["institution_name"] == "BLACKROCK INC"
        assert result[0]["report_date"] == "2025-02-14"

    @patch("app.services.edgar_client.requests.Session.get")
    def test_institutional_holders_deduplicates(self, mock_get: MagicMock):
        mock_search_resp = MagicMock()
        mock_search_resp.status_code = 200
        mock_search_resp.json.return_value = {
            "hits": {
                "hits": [
                    {"_source": {"entity_name": "VANGUARD GROUP", "file_date": "2025-02-14"}},
                    {"_source": {"entity_name": "VANGUARD GROUP", "file_date": "2025-01-14"}},
                    {"_source": {"entity_name": "BLACKROCK INC", "file_date": "2025-02-10"}},
                ]
            }
        }

        mock_get.return_value = mock_search_resp

        client = EdgarClient()
        result = client.get_institutional_holders("AAPL")

        assert result is not None
        assert len(result) == 2  # Duplicate VANGUARD GROUP removed

    @patch("app.services.edgar_client.requests.Session.get")
    def test_institutional_holders_caching(self, mock_get: MagicMock):
        mock_search_resp = MagicMock()
        mock_search_resp.status_code = 200
        mock_search_resp.json.return_value = {"hits": {"hits": []}}

        mock_get.return_value = mock_search_resp

        client = EdgarClient()
        client.get_institutional_holders("AAPL")
        call_count_after_first = mock_get.call_count
        client.get_institutional_holders("AAPL")  # should hit cache
        assert mock_get.call_count == call_count_after_first
