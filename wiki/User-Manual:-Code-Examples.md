# Code Examples

API usage examples in multiple languages. All examples use the public endpoint without authentication. Add the `Authorization: Bearer <token>` header for authenticated requests.

**Base URL:** `https://www.instnews.net`

---

## cURL

### Get latest 10 news items

```bash
curl -s "https://www.instnews.net/api/news?limit=10" | jq .
```

### Search for NVIDIA news

```bash
curl -s "https://www.instnews.net/api/news?q=nvidia&limit=5" | jq .
```

### Get bullish headlines only

```bash
curl -s "https://www.instnews.net/api/news?sentiment=bullish&limit=10" | jq .
```

### Filter by source

```bash
curl -s "https://www.instnews.net/api/news?source=CNBC&limit=10" | jq .
```

### Force refresh

```bash
curl -s -X POST "https://www.instnews.net/api/refresh" | jq .
```

### Get statistics

```bash
curl -s "https://www.instnews.net/api/stats" | jq .
```

---

## Python

### Basic Usage

```python
import requests

BASE_URL = "https://www.instnews.net"

# Get latest news
response = requests.get(f"{BASE_URL}/api/news", params={"limit": 10})
data = response.json()

for item in data["items"]:
    print(f"[{item['source']}] {item['title']}")
    print(f"  {item['link']}")
    print()
```

### Search and Filter

```python
import requests

BASE_URL = "https://www.instnews.net"

# Search for a keyword
response = requests.get(f"{BASE_URL}/api/news", params={
    "q": "Federal Reserve",
    "limit": 20,
})

for item in response.json()["items"]:
    print(f"{item['published']} — {item['title']}")
```

### Authenticated Request (Plus/Max)

```python
import requests

BASE_URL = "https://www.instnews.net"
TOKEN = "your_firebase_id_token"

headers = {"Authorization": f"Bearer {TOKEN}"}

# Get news with sentiment data (Plus/Max only)
response = requests.get(
    f"{BASE_URL}/api/news",
    params={"limit": 50, "sentiment": "bullish"},
    headers=headers,
)

for item in response.json()["items"]:
    score = item.get("sentiment_score", "N/A")
    print(f"[{score:+.2f}] {item['title']}")
```

### Continuous Polling (Trading Bot)

```python
import time
import requests

BASE_URL = "https://www.instnews.net"
seen_ids = set()

while True:
    try:
        response = requests.get(f"{BASE_URL}/api/news", params={"limit": 50})
        data = response.json()

        for item in data["items"]:
            if item["id"] not in seen_ids:
                seen_ids.add(item["id"])
                print(f"NEW: [{item['source']}] {item['title']}")
                # → trigger your trading logic here

    except requests.RequestException as e:
        print(f"Error: {e}")

    time.sleep(5)  # poll every 5 seconds
```

---

## JavaScript / Node.js

### Basic Fetch

```javascript
const BASE_URL = "https://www.instnews.net";

async function getLatestNews(limit = 10) {
  const response = await fetch(`${BASE_URL}/api/news?limit=${limit}`);
  const data = await response.json();

  data.items.forEach(item => {
    console.log(`[${item.source}] ${item.title}`);
  });

  return data;
}

getLatestNews();
```

### With Authentication

```javascript
const BASE_URL = "https://www.instnews.net";

async function getNews(token, params = {}) {
  const query = new URLSearchParams(params).toString();
  const response = await fetch(`${BASE_URL}/api/news?${query}`, {
    headers: {
      "Authorization": `Bearer ${token}`,
    },
  });
  return response.json();
}

// Usage
const data = await getNews("your_firebase_token", {
  limit: 50,
  sentiment: "bearish",
  q: "oil",
});
```

### WebSocket-style Polling

```javascript
const BASE_URL = "https://www.instnews.net";
const seenIds = new Set();

async function pollNews() {
  try {
    const response = await fetch(`${BASE_URL}/api/news?limit=50`);
    const data = await response.json();

    for (const item of data.items) {
      if (!seenIds.has(item.id)) {
        seenIds.add(item.id);
        console.log(`NEW: [${item.source}] ${item.title}`);
        // → trigger callback here
      }
    }
  } catch (err) {
    console.error("Poll error:", err);
  }
}

setInterval(pollNews, 5000); // every 5 seconds
```

---

## Go

```go
package main

import (
	"encoding/json"
	"fmt"
	"net/http"
	"net/url"
)

const baseURL = "https://www.instnews.net"

type NewsResponse struct {
	Count int        `json:"count"`
	Items []NewsItem `json:"items"`
}

type NewsItem struct {
	ID             int     `json:"id"`
	Title          string  `json:"title"`
	Link           string  `json:"link"`
	Source         string  `json:"source"`
	Published      string  `json:"published"`
	Summary        string  `json:"summary"`
	SentimentScore float64 `json:"sentiment_score,omitempty"`
	SentimentLabel string  `json:"sentiment_label,omitempty"`
	Duplicate      int     `json:"duplicate,omitempty"`
}

func getNews(query string, limit int) (*NewsResponse, error) {
	params := url.Values{}
	params.Set("limit", fmt.Sprintf("%d", limit))
	if query != "" {
		params.Set("q", query)
	}

	resp, err := http.Get(fmt.Sprintf("%s/api/news?%s", baseURL, params.Encode()))
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()

	var result NewsResponse
	if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
		return nil, err
	}
	return &result, nil
}

func main() {
	news, err := getNews("NVIDIA", 5)
	if err != nil {
		fmt.Printf("Error: %v\n", err)
		return
	}

	for _, item := range news.Items {
		fmt.Printf("[%s] %s\n", item.Source, item.Title)
	}
}
```

---

## R

```r
library(httr)
library(jsonlite)

base_url <- "https://www.instnews.net"

# Get latest bullish news
response <- GET(
  paste0(base_url, "/api/news"),
  query = list(sentiment = "bullish", limit = 20)
)

data <- fromJSON(content(response, "text"))

# View as data frame
df <- data$items
print(df[, c("published", "source", "title", "sentiment_score")])

# Plot sentiment distribution
stats <- GET(paste0(base_url, "/api/stats"))
stats_data <- fromJSON(content(stats, "text"))
barplot(
  unlist(stats_data$by_sentiment),
  main = "News Sentiment Distribution",
  col = c("red", "green", "yellow")
)
```

---

## Rust

```rust
use reqwest;
use serde::Deserialize;

#[derive(Debug, Deserialize)]
struct NewsResponse {
    count: u32,
    items: Vec<NewsItem>,
}

#[derive(Debug, Deserialize)]
struct NewsItem {
    id: u64,
    title: String,
    link: String,
    source: String,
    published: String,
    summary: String,
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let url = "https://www.instnews.net/api/news?limit=5&q=earnings";
    let response: NewsResponse = reqwest::get(url).await?.json().await?;

    for item in &response.items {
        println!("[{}] {}", item.source, item.title);
        println!("  {}\n", item.link);
    }

    Ok(())
}
```

---

## Common Patterns

### Pagination

The API does not use cursor-based pagination. To page through results, adjust the `from`/`to` date range (Plus/Max) or use the `published` timestamp of the last item.

```python
# Get next page by using the last item's timestamp as the upper bound
last_published = data["items"][-1]["published"]
next_page = requests.get(f"{BASE_URL}/api/news", params={
    "to": last_published,
    "limit": 50,
})
```

### Error Handling

```python
response = requests.get(f"{BASE_URL}/api/news")

if response.status_code == 200:
    data = response.json()
elif response.status_code == 403:
    error = response.json()
    print(f"Upgrade required: {error['upgrade_url']}")
elif response.status_code == 429:
    retry_after = response.headers.get("Retry-After", 60)
    time.sleep(int(retry_after))
else:
    print(f"Error {response.status_code}: {response.text}")
```
