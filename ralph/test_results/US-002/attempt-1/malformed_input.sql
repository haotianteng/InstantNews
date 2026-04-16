BEGIN;
UPDATE news SET sentiment_score = 0.5, sentiment_label = 'positive', target_asset = 'AAPL', asset_type = 'stock', confidence = 0.9, risk_level = 'low', tradeable = TRUE, reasoning = 'test', ai_analyzed = TRUE WHERE link = 'https://nonexistent-article-12345.example.com';
THIS IS INVALID SQL;
COMMIT;
