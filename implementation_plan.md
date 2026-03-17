# 全市場掃描 + 本地快取 — 實施計畫

## 問題

- FinMind 無 stock_id 的批量 API 需要 Sponsor 等級
- 使用者帳號為 Register 等級 (600 req/hr)
- 約 1,800 檔上市櫃股票（排除 ETF/權證/興櫃）需要多次 API 呼叫

## 設計方案

> [!IMPORTANT]
> **API 限速策略**：Register 等級每小時 600 次請求。每檔股票需 ~4 次 API 呼叫（價格 + 法人 + 融資 + PER）。
> - 首次完整抓取 ~1,800 股 × 4 = ~7,200 次 → 分 **12 批次**，每批 ~150 股
> - 後續每日更新只抓「最後快取日 → 今天」的差量資料

### 快取架構

```
Stock_base_data/
├── stock_info.csv             # 股票總覽 (每日更新)
├── daily_price.csv            # 所有股票日K (增量追加)
├── institutional.csv          # 三大法人 (增量追加)
├── margin.csv                 # 融資融券 (增量追加)
├── per_pbr.csv                # PER/PBR (增量追加)
├── revenue.csv                # 月營收 (增量追加)
└── cache_meta.json            # 快取狀態 (最後更新日、進度)
```

### 核心邏輯

1. **首次執行** → 依批次逐步抓取所有股票，每批 150 檔，中間自動暫停避免限速
2. **後續執行** → 讀 `cache_meta.json` 的 `last_date`，只抓新資料並 append
3. 分析時直接讀本地 CSV，不再呼叫 API

## Proposed Changes

### [NEW] [stock_cache.py](file:///d:/Jay%20PhD/Code/stock/stock_cache.py)
- `StockCache` 類別：初始化 / 增量更新 / 讀取本地資料
- 批次抓取 + 自動限速 + 進度條
- 支援斷點續傳（記錄已完成的批次）

### [MODIFY] [data_fetcher.py](file:///d:/Jay%20PhD/Code/stock/data_fetcher.py)
- 新增 `get_daily_price_all(date)` — 逐股抓取所有股票指定日期價格
- 新增 `get_institutional_all_by_stock(stock_ids, start, end)` — 批次抓法人資料

### [MODIFY] [ai_analyst.py](file:///d:/Jay%20PhD/Code/stock/ai_analyst.py)
- 新增 `run_full_market_scan()` — 全市場掃描模式，從 Cache 讀取
- 族群輪動改用 Cache 裡的全市場法人資料

### [MODIFY] [main.py](file:///d:/Jay%20PhD/Code/stock/main.py)
- 新增 `--init-cache` 首次建立快取
- 新增 `--update-cache` 增量更新快取
- 新增 `--full-scan` 全市場分析

## Verification

```bash
python main.py --init-cache       # 首次建快取 (約需多批次)
python main.py --update-cache     # 每日增量更新
python main.py --full-scan        # 全市場分析 + 族群輪動
```
