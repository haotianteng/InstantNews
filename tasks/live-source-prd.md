# InstNews 一手新闻源采集系统 — PRD

**Product:** InstNews Source Acquisition Pipeline  
**Version:** 1.0  
**Date:** 2026-04-13  
**Author:** Havens  

---

## 1. 产品概述

InstNews 是一个实时市场新闻信号平台，核心价值主张是**绕过二手媒体中间商（CNBC、Bloomberg 等），直接从一手信源采集、转录、提取结构化交易信号**，以最低延迟交付给订阅用户和下游系统（AgenticTrader）。

### 1.1 核心原则

- **一手优先**：只有信息的原始产出方才算一手源（发言人本人、监管机构官方发布、公司 IR 页面）。媒体报道、分析师转述均为二手，仅在采访当事人时例外。
- **延迟即 Alpha**：端到端目标 < 7 秒（从直播发生到信号输出）。
- **信号而非内容**：不转售原始文本或音频，只输出结构化 JSON 交易信号，规避版权风险。

### 1.2 目标用户

| 用户类型 | 使用方式 |
|---------|---------|
| AgenticTrader（内部） | 通过 WebSocket 接收信号，自动交易决策 |
| InstNews Plus/Max 订阅者 | 通过 Web/App 接收实时信号推送 |
| 量化研究员 | 通过 REST API 回溯历史信号数据 |

---

## 2. 数据源定义与优先级

### 2.1 Tier 1 — 政府/监管（最高优先级）

这些源直接影响整体市场走向，必须在 MVP 中覆盖。

| 源 | 数据类型 | 采集方式 | 预期延迟 |
|----|---------|---------|---------|
| **SEC EDGAR** | 8-K、4、13F 文件 | EDGAR Full-Text RSS Feed 轮询（10s 间隔） | < 15s |
| **Federal Reserve** | FOMC 声明、利率决议 | federalreserve.gov 页面监控 + YouTube 直播 ASR | 声明: < 5s / 记者会: < 7s |
| **Treasury.gov** | 拍卖结果、制裁公告 | RSS + 页面变更监控 | < 15s |
| **C-SPAN** | 白宫记者会、国会听证、Fed 主席作证 | HLS 流采集 → ASR | < 7s |
| **WhiteHouse.gov/live** | 总统讲话、政策声明 | HLS 流采集 → ASR | < 7s |

### 2.2 Tier 2 — 企业直接源

Earnings Season 期间为最高优先级，平时按需调度。

| 源 | 数据类型 | 采集方式 | 预期延迟 |
|----|---------|---------|---------|
| **公司 IR 页面 Webcast** | 财报电话会、Investor Day | Playwright 发现流地址 → ffmpeg → ASR | < 7s |
| **GlobeNewswire / PR Newswire / BusinessWire** | 公司公告、并购、管理层变动 | RSS Feed + Webhook | < 10s |
| **CEO/高管 Twitter/X** | 一手发言 | Twitter API v2 Filtered Stream | < 3s |

### 2.3 Tier 3 — 直播电视（条件性一手）

仅在采访信息原始当事人时视为一手，其余视为二手信号用于交叉验证。

| 源 | 采集方式 | 成本 |
|----|---------|------|
| **Bloomberg TV**（Pluto TV / Tubi） | HLS 流 → ASR | 免费 |
| **CNBC / Fox Business**（Sling Blue） | App 内 HLS 流 → ASR | $52/月 |

### 2.4 Tier 4 — 辅助源（信号增强）

| 源 | 用途 | 采集方式 |
|----|------|---------|
| **Polygon.io**（$29/月 Starter） | 行情上下文、前端图表 | REST API |
| **FRED / BLS / BEA** | 宏观经济数据发布 | RSS + 定时抓取 |
| **PACER/RECAP** | 重大诉讼（反垄断、破产） | 定时抓取 |

---

## 3. 系统架构

### 3.1 整体流水线

```
┌──────────────────────────────────────────────────┐
│  Source Discovery Layer                          │
│  Playwright (headless) 发现 .m3u8 / 流地址        │
│  EDGAR RSS / Twitter API / 页面变更监控            │
└──────────────────┬───────────────────────────────┘
                   │ stream URLs / raw text / filings
                   ▼
┌──────────────────────────────────────────────────┐
│  Capture Layer                                   │
│  ├── ffmpeg 多实例: HLS .m3u8 → raw audio chunks │
│  ├── HTTP poller: EDGAR / Treasury / GlobeNewswire│
│  └── WebSocket: Twitter Filtered Stream           │
└──────────────────┬───────────────────────────────┘
                   │ audio chunks / raw text
                   ▼
┌──────────────────────────────────────────────────┐
│  Transcription Layer (ASR)                       │
│  Deepgram Nova-2 Streaming (~300ms latency)      │
│  仅用于音频源；文本源直接跳过此层                    │
└──────────────────┬───────────────────────────────┘
                   │ transcript text
                   ▼
┌──────────────────────────────────────────────────┐
│  Signal Extraction Layer (LLM)                   │
│  ├── NER: ticker / 公司 / 人物 / 政策术语          │
│  ├── 情感打分 (per entity)                        │
│  ├── 事件分类: earnings / M&A / Fed / macro / geo │
│  ├── 新颖性检测: breaking vs. rehash              │
│  └── 影响力评分: 来源可信度 × 情感强度 × 类别权重   │
└──────────────────┬───────────────────────────────┘
                   │ structured signal JSON
                   ▼
┌──────────────────────────────────────────────────┐
│  Event Bus (Redis Streams)                       │
│  ├── 去重 (cross-source dedup)                    │
│  ├── 时间衰减优先队列                              │
│  └── Consumer Groups → API / WebSocket / Storage  │
└──────────────────┬───────────────────────────────┘
                   │
          ┌────────┼────────┐
          ▼        ▼        ▼
      FastAPI   WebSocket  TimescaleDB
     (REST)    (实时推送)   (历史存储)
```

### 3.2 信号输出 Schema

```json
{
  "signal_id": "uuid-v4",
  "timestamp": "2026-04-13T14:30:01.234Z",
  "source": {
    "type": "government",
    "name": "Federal Reserve",
    "url": "https://www.federalreserve.gov/...",
    "is_first_hand": true
  },
  "entities": [
    {
      "name": "Federal Reserve",
      "type": "institution",
      "ticker": null
    }
  ],
  "tickers_affected": ["SPY", "TLT", "GLD", "DXY"],
  "event_type": "rate_decision",
  "headline": "Fed holds rates steady at 4.25-4.50%",
  "sentiment": {
    "score": 0.15,
    "label": "slightly_hawkish"
  },
  "impact_score": 9.2,
  "novelty": "breaking",
  "raw_excerpt": "The Committee decided to maintain the target range...",
  "confidence": 0.94,
  "latency_ms": 4520
}
```

---

## 4. 核心模块详细需求

### 4.1 Source Discovery（流地址发现）

**功能**：使用 Playwright headless 浏览器自动发现直播页面中的 HLS `.m3u8` 流地址。

**需求**：

- R-4.1.1：支持预配置源列表（C-SPAN、WhiteHouse.gov、Fed YouTube 等），定时检查是否有活跃直播。
- R-4.1.2：监听页面网络请求，自动过滤包含 `.m3u8` 的 URL。
- R-4.1.3：发现新流后，自动注册到 Capture Layer，启动 ffmpeg 实例。
- R-4.1.4：直播结束后自动检测流断开，清理资源。
- R-4.1.5：支持 YouTube 直播（通过 yt-dlp 提取流地址）。

**参考实现**：

```python
from playwright.sync_api import sync_playwright

def discover_stream(url):
    streams = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.on("request", lambda req:
            streams.append(req.url) if ".m3u8" in req.url else None)
        page.goto(url)
        page.wait_for_timeout(5000)
    return streams
```

### 4.2 Audio Capture（音频采集）

**功能**：将 HLS 流转为原始音频流，管道输入 ASR。

**需求**：

- R-4.2.1：每个活跃流启动一个独立 ffmpeg 进程。
- R-4.2.2：输出格式为 16kHz mono WAV PCM（Deepgram 最佳输入格式）。
- R-4.2.3：支持同时运行 ≥ 10 个并发流采集。
- R-4.2.4：ffmpeg 进程异常退出时自动重启（watchdog 机制）。
- R-4.2.5：不落盘，直接通过 pipe 传递音频数据。

**参考命令**：

```bash
ffmpeg -i "https://xxx.m3u8" \
  -vn -acodec pcm_s16le -ar 16000 -ac 1 \
  -f wav pipe:1
```

### 4.3 ASR Transcription（语音转文字）

**功能**：将实时音频流转为文本。

**需求**：

- R-4.3.1：使用 Deepgram Nova-2 Streaming API 作为主 ASR 引擎。
- R-4.3.2：转录延迟 ≤ 500ms（从音频输入到文本输出）。
- R-4.3.3：启用 interim results，允许 LLM 层在句子完成前开始处理。
- R-4.3.4：支持 speaker diarization（区分发言人，用于记者会 Q&A 场景）。
- R-4.3.5：Deepgram 不可用时降级到本地 Whisper（faster-whisper, 5-10s 分段）。

### 4.4 LLM Signal Extraction（信号提取）

**功能**：从转录文本/原始文本中提取结构化交易信号。

**需求**：

- R-4.4.1：主模型使用 Claude Haiku 或 GPT-4o-mini（延迟 800ms-1.5s，成本 ~$0.01-0.05/次）。
- R-4.4.2：提取字段符合 Section 3.2 定义的 Signal Schema。
- R-4.4.3：支持 ticker 模糊匹配（"the iPhone maker" → AAPL）。
- R-4.4.4：新颖性检测：与最近 1 小时信号对比，标记 breaking / update / rehash。
- R-4.4.5：影响力评分公式：`来源可信度权重 × 情感强度 × 类别重要性 × 相关 ticker 流动性 × 时段因子`。
- R-4.4.6：对模糊/低信心段落，升级到更强模型（Claude Sonnet）进行二次判断。

### 4.5 Text Source Ingestion（文本源采集）

**功能**：采集非音频的文本一手源。

**需求**：

- R-4.5.1：SEC EDGAR — 通过 Full-Text RSS Feed 轮询，间隔 ≤ 10 秒。
- R-4.5.2：Treasury.gov — 页面变更监控（hash diff），间隔 ≤ 30 秒。
- R-4.5.3：GlobeNewswire / PR Newswire — RSS Feed 轮询，间隔 ≤ 15 秒。
- R-4.5.4：Twitter/X — 使用 Filtered Stream API v2，关键词过滤（$TICKER、高管账号列表）。
- R-4.5.5：Fed 声明 — federalreserve.gov 页面监控，FOMC 日加密轮询至 1 秒间隔。
- R-4.5.6：文本源直接进入 LLM Signal Extraction，跳过 ASR 层。

### 4.6 Event Bus & Deduplication（事件总线与去重）

**需求**：

- R-4.6.1：使用 Redis Streams 作为中心事件总线。
- R-4.6.2：跨源去重：基于 entity + event_type + 时间窗口（60s）的相似度匹配。
- R-4.6.3：时间衰减优先队列（复用 AgenticTrader 架构）：新信号权重随时间指数衰减。
- R-4.6.4：支持 Consumer Groups，允许多个下游消费者独立消费（API Server、WebSocket、存储、AgenticTrader）。

---

## 5. 延迟预算

| 阶段 | 目标延迟 | 说明 |
|------|---------|------|
| 直播流固有延迟 | 2-5s | HLS 分段 + CDN 缓冲，不可控 |
| 流地址发现 | 0ms | 预发现，直播开始前已就绪 |
| ffmpeg 音频提取 | ~100ms | pipe 模式，无落盘 |
| Deepgram ASR | ~300ms | Nova-2 streaming，含 interim results |
| LLM 信号提取 | ~1000ms | Claude Haiku / GPT-4o-mini |
| Redis 发布 + 推送 | ~50ms | 本地 Redis |
| **端到端总延迟** | **3.5 - 6.5s** | 从直播事件发生到信号送达用户 |

**对比基准**：人类交易员观看 CNBC 后手动反应需 10-30 秒，InstNews 用户至少领先 5-25 秒。

---

## 6. 基础设施

### 6.1 部署架构（MVP）

| 组件 | 规格 | 成本 |
|------|------|------|
| **主服务器** | Hetzner AX52（64GB RAM, 8 核 AMD Ryzen） | ~$60/月 |
| **编排** | Docker Compose | — |
| **ASR** | Deepgram Pay-as-you-go | ~$0.0043/分钟 |
| **LLM** | Claude Haiku API | ~$0.01-0.05/次提取 |
| **行情上下文** | Polygon.io Starter | $29/月 |
| **直播电视**（可选） | Sling Blue + News Extra | $52/月 |
| **域名/CDN** | Cloudflare | 免费 |

**MVP 月度运营成本估算**：~$150-250/月（不含直播电视订阅）

### 6.2 存储

| 层 | 技术 | 用途 |
|----|------|------|
| Hot Cache | Redis | 最近 1 小时信号，实时去重 |
| Time-series | PostgreSQL + TimescaleDB | 全部历史信号，支持范围查询 |
| Archive | S3（Hetzner Storage Box） | 原始转录文本，回测数据集 |

### 6.3 API

| 端点 | 协议 | 用途 |
|------|------|------|
| `GET /signals` | REST (FastAPI) | 历史信号查询，支持 ticker/时间/类型过滤 |
| `WS /signals/stream` | WebSocket | 实时信号推送给订阅用户 |
| `GET /signals/sse` | SSE | 轻量级实时推送（浏览器友好） |

---

## 7. MVP 范围与里程碑

### Phase 1 — 文本源 MVP（2 周）

- [ ] SEC EDGAR RSS 轮询 + LLM 信号提取
- [ ] Fed/Treasury 页面变更监控
- [ ] GlobeNewswire/PR Newswire RSS
- [ ] Redis Streams 事件总线 + 去重
- [ ] FastAPI + WebSocket 信号分发
- [ ] 基础前端信号展示

**交付物**：能在 FOMC 声明发布后 < 15 秒输出结构化信号。

### Phase 2 — 音频源（2 周）

- [ ] Playwright 流地址发现（C-SPAN, Fed YouTube）
- [ ] ffmpeg → Deepgram 音频管道
- [ ] ASR 输出 → LLM 信号提取对接
- [ ] 多流并发管理 + watchdog
- [ ] Speaker diarization 集成

**交付物**：能实时转录 C-SPAN 听证会并输出信号。

### Phase 3 — 信号增强（2 周）

- [ ] Twitter/X Filtered Stream 集成
- [ ] Polygon.io 行情上下文注入（信号中附带当前价格/变动）
- [ ] 影响力评分模型校准（基于历史 news→price 数据）
- [ ] 新颖性检测优化
- [ ] Earnings call webcast 自动发现 + 采集

**交付物**：完整的多源信号管道，覆盖政府 + 企业 + 社交。

### Phase 4 — 商业化（2 周）

- [ ] Stripe 订阅集成（Plus/Max 分层）
- [ ] 用户认证 + API Key 管理
- [ ] Rate limiting（按订阅层级）
- [ ] 信号历史回放 API
- [ ] 监控面板（源状态、延迟、信号量）

---

## 8. 风险与缓解

| 风险 | 影响 | 概率 | 缓解措施 |
|------|------|------|---------|
| HLS 流地址变更 | 采集中断 | 中 | Playwright 动态发现，不硬编码 URL |
| Deepgram 服务中断 | ASR 不可用 | 低 | 降级到本地 faster-whisper |
| LLM API 延迟飙升 | 超出延迟预算 | 中 | 本地 Llama 3 做快速预筛，仅模糊案例调用云端 |
| SEC/政府网站改版 | 文本采集失效 | 低 | EDGAR 有稳定 RSS feed；其他源用结构化选择器 + 告警 |
| 直播电视 ToS/DRM | 法律风险 | 中 | 仅输出信号不转售内容；优先使用免费公开源（C-SPAN, Pluto TV）；付费源仅内部使用 |
| Twitter API 限流/涨价 | 社交源受限 | 高 | Twitter 为辅助源非核心依赖；可降级为 RSS 抓取公开账号 |

---

## 9. 成功指标

| 指标 | MVP 目标 | 6 个月目标 |
|------|---------|-----------|
| 端到端延迟（P95） | < 7s | < 5s |
| 信号准确率（entity + sentiment） | > 85% | > 92% |
| 源覆盖（活跃源数量） | 5+ | 15+ |
| 系统可用性 | 95% | 99.5% |
| 去重准确率 | > 90% | > 97% |
| 日均信号产出 | 50+ | 500+ |

---

## 10. 不在范围内

- 原始音频/视频存储与回放（仅存信号和转录摘要）
- 自研 ASR 模型（使用 Deepgram 托管服务）
- 国际市场新闻源（Phase 1-4 仅覆盖美国市场）
- 移动端 App（MVP 阶段仅 Web + API）
- 实时行情数据分发（行情由 Polygon 或 IBKR 提供，InstNews 专注新闻信号）