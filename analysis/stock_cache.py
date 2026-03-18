"""
AI 台股分析師 — 本地資料快取模組
自動管理 Stock_base_data 目錄：首次建立完整快取，後續只追加新日期資料
"""
import os
import json
import time
import pandas as pd
from datetime import datetime, timedelta
from data_fetcher import StockDataFetcher
from config import FINMIND_API_TOKEN

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
CACHE_DIR = os.path.join(PROJECT_ROOT, "stock_data")
META_FILE = os.path.join(CACHE_DIR, "cache_meta.json")


# 每批抓取股票數（避免 API 限速）
BATCH_SIZE = 100
# 每次 API 呼叫間隔 (秒)
API_DELAY = 0.3
# 每批次完成後暫停 (秒)
BATCH_DELAY = 5


class StockCache:
    """本地 CSV 快取管理器"""

    def __init__(self, api_delay: float = 0.3, batch_delay: float = 5.0, use_yfinance: bool = False):
        """
        use_yfinance: True → 日K線改用 yfinance 下載 (FinMind 額度耗盡時使用)。
                      籌碼/基本面資料仍嘗試 FinMind，但若同樣額度耗盡則跳過。
        """
        os.makedirs(CACHE_DIR, exist_ok=True)

        self.fetcher = StockDataFetcher(use_yfinance=use_yfinance)
        self.meta = self._load_meta()
        self.api_delay = api_delay
        self.batch_delay = batch_delay
        self.use_yfinance = use_yfinance

        if use_yfinance:
            print("📡 [yfinance 模式] 日K線將使用 yfinance 下載，籌碼/基本面仍走 FinMind (可能跳過)。")

        
        # In-memory caches for fast full-market scanning
        self._memory_cache = {
            "daily_price": None,
            "margin": None,
            "per_pbr": None,
            "revenue": None,
            "financial": None
        }

    # ─── Meta 管理 ──────────────────────────────────────────────

    def _load_meta(self) -> dict:
        if os.path.exists(META_FILE):
            with open(META_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        return {
            "initialized": False,
            "last_update": None,
            "last_price_date": None,
            "last_margin_date": None,
            "last_per_date": None,
            "last_revenue_date": None,
            "last_financial_date": None,
            "stock_count": 0,
            "batch_progress": 0,  # 斷點續傳: 已完成批次 (init_cache)
            "update_progress": 0, # 斷點續傳: 已完成序號 (update_cache)
        }

    def _save_meta(self):
        with open(META_FILE, "w", encoding="utf-8") as f:
            json.dump(self.meta, f, ensure_ascii=False, indent=2)

    def is_initialized(self) -> bool:
        """檢查快取是否已初始化完畢"""
        return self.meta.get("initialized", False)

    # ─── 股票清單 ───────────────────────────────────────────────

    def _get_target_stocks(self) -> pd.DataFrame:
        """取得所有上市櫃股票（排除 ETF / 權證 / 興櫃）"""
        info_path = os.path.join(CACHE_DIR, "stock_info.csv")
        
        # 優先從本地讀取，避免 API 故障
        if os.path.exists(info_path):
            try:
                info = pd.read_csv(info_path, dtype={"stock_id": str})
                if not info.empty and "type" in info.columns:
                    print(f"  🎬 從本地載入股票清單 ({len(info)} 檔)")
                else:
                    info = self.fetcher.get_stock_info()
            except Exception:
                info = self.fetcher.get_stock_info()
        else:
            info = self.fetcher.get_stock_info()

        if info is None or info.empty or "type" not in info.columns:
            print("❌ 無法取得有效的股票資訊清單")
            return pd.DataFrame()

        # 只有在資料有效時才更新本地檔案
        info.to_csv(info_path, index=False, encoding="utf-8-sig")

        # 過濾: 只保留上市(twse)和上櫃(tpex), 排除 ETF
        listed = info[info["type"].isin(["twse", "tpex"])].copy()
        # 排除 ETF 類
        if "industry_category" in listed.columns:
            etf_keywords = ["ETF", "上櫃ETF", "ETN"]
            listed = listed[~listed["industry_category"].isin(etf_keywords)]
        
        # 排除股票代碼非純數字的 (排除權證等)
        if "stock_id" in listed.columns:
            listed = listed[listed["stock_id"].str.match(r"^\d{4}$", na=False)]

        return listed

    # ─── 初始化快取 ─────────────────────────────────────────────

    def init_cache(self, lookback_days: int = 180):
        """
        首次全市場資料建立
        lookback_days: 往回抓幾天的資料 (預設 180 天)
        """
        print("\n" + "=" * 60)
        print("  📦 Stock_base_data 快取初始化")
        print("=" * 60)

        stocks_df = self._get_target_stocks()
        if stocks_df.empty:
            print("❌ 無法繼續初始化：找不到任何有效的股票清單。")
            print("   請確認網路連線或 FinMind API 狀態。")
            return
            
        stock_ids = stocks_df["stock_id"].tolist()
        total = len(stock_ids)
        print(f"\n  📊 目標股票: {total} 檔 (上市+上櫃，排除 ETF/權證)")

        start_date = (datetime.now() - timedelta(days=lookback_days)).strftime("%Y-%m-%d")
        start_date_revenue = (datetime.now() - timedelta(days=400)).strftime("%Y-%m-%d")
        end_date = datetime.now().strftime("%Y-%m-%d")
        print(f"  📅 資料區間: {start_date} ~ {end_date} (財報營收往前400天)")

        # 分批
        batches = [stock_ids[i:i + BATCH_SIZE] for i in range(0, total, BATCH_SIZE)]
        total_batches = len(batches)
        start_batch = self.meta.get("batch_progress", 0)

        if start_batch > 0:
            print(f"  🔄 斷點續傳: 從第 {start_batch + 1}/{total_batches} 批繼續")

        # API 呼叫估算
        remaining_stocks = sum(len(b) for b in batches[start_batch:])
        est_calls = remaining_stocks * 4  # 4 datasets per stock
        est_minutes = est_calls * self.api_delay / 60
        print(f"  ⏱️ 預估 API 呼叫: {est_calls} 次，約需 {est_minutes:.0f} 分鐘")
        print(f"  ⚡ API 間隔: {self.api_delay}s，每批 {BATCH_SIZE} 檔暫停 {self.batch_delay}s")
        print()

        all_price = []
        all_inst = []
        all_margin = []
        all_per = []
        all_rev = []
        all_fin = []

        for batch_idx in range(start_batch, total_batches):
            batch = batches[batch_idx]
            batch_start = batch_idx * BATCH_SIZE + 1
            batch_end = min((batch_idx + 1) * BATCH_SIZE, total)
            print(f"  📥 批次 {batch_idx + 1}/{total_batches} ({batch_start}-{batch_end}/{total})")

            for j, sid in enumerate(batch):
                progress = f"[{batch_start + j}/{total}]"
                print(f"\r    {progress} {sid}...", end="", flush=True)

                # 日K線
                try:
                    df = self.fetcher.get_daily_price(sid, start_date, end_date)
                    if df is not None and len(df) > 0:
                        all_price.append(df)
                except Exception as e:
                    if self._is_quota_error(e):
                        print(f"\n🛑 [STOP] API 額度已耗盡。已儲存目前進度 (批次 {batch_idx})，請一小時後再試。")
                        self.meta["batch_progress"] = batch_idx
                        self._save_meta()
                        return False
                    pass
                time.sleep(self.api_delay)

                # 三大法人
                try:
                    df = self.fetcher.get_institutional(sid, start_date, end_date)
                    if df is not None and len(df) > 0:
                        all_inst.append(df)
                except Exception as e:
                    if self._is_quota_error(e):
                        print(f"\n🛑 [STOP] API 額度已耗盡。已儲存進度。")
                        self.meta["batch_progress"] = batch_idx
                        self._save_meta()
                        return False
                    pass
                time.sleep(self.api_delay)

                # 融資融券
                try:
                    df = self.fetcher.get_margin(sid, start_date, end_date)
                    if df is not None and len(df) > 0:
                        all_margin.append(df)
                except Exception as e:
                    if self._is_quota_error(e):
                        print(f"\n🛑 [STOP] API 額度已耗盡。")
                        self.meta["batch_progress"] = batch_idx
                        self._save_meta()
                        return False
                    pass
                time.sleep(self.api_delay)

                # PER/PBR
                try:
                    df = self.fetcher.get_per_pbr(sid, start_date, end_date)
                    if df is not None and len(df) > 0:
                        all_per.append(df)
                except Exception:
                    pass
                time.sleep(self.api_delay)

                # 月營收
                try:
                    df = self.fetcher.get_revenue(sid, start_date_revenue, end_date)
                    if df is not None and len(df) > 0:
                        all_rev.append(df)
                except Exception:
                    pass
                time.sleep(self.api_delay)

                # 財報
                try:
                    df = self.fetcher.get_financial(sid, start_date_revenue, end_date)
                    if df is not None and len(df) > 0:
                        all_fin.append(df)
                except Exception:
                    pass
                time.sleep(self.api_delay)

            print()  # newline after batch

            # 每批完成後存檔 (防止中斷遺失)
            self._save_batch(all_price, all_inst, all_margin, all_per, all_rev, all_fin)
            all_price, all_inst, all_margin, all_per, all_rev, all_fin = [], [], [], [], [], []

            # 更新進度
            self.meta["batch_progress"] = batch_idx + 1
            self._save_meta()

            if batch_idx < total_batches - 1:
                print(f"    💤 暫停 {self.batch_delay}s (API 限速)...")
                time.sleep(self.batch_delay)

        # 完成
        self.meta["initialized"] = True
        self.meta["last_update"] = end_date
        self.meta["last_price_date"] = end_date
        self.meta["last_institutional_date"] = end_date
        self.meta["last_margin_date"] = end_date
        self.meta["last_per_date"] = end_date
        self.meta["last_revenue_date"] = end_date
        self.meta["last_financial_date"] = end_date
        self.meta["stock_count"] = total
        self.meta["batch_progress"] = 0  # reset
        self._save_meta()

        print(f"\n  ✅ 快取初始化完成！")
        self._print_cache_status()
        return True

    # ─── 增量更新 ───────────────────────────────────────────────

    def update_cache(self):
        """每日增量更新: 只抓 last_update 之後的新資料"""
        if not self.meta.get("initialized"):
            print("❌ 快取尚未初始化，請先執行 --init-cache")
            return False

        last = self.meta.get("last_update")
        today = datetime.now().strftime("%Y-%m-%d")

        if last == today:
            print(f"✅ 快取已是最新 ({today})")
            return True

        # 從 last_update 的隔天開始
        start_date = (datetime.strptime(last, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")
        end_date = today

        print(f"\n📥 增量更新: {start_date} ~ {end_date}")

        stocks_df = self._get_target_stocks()
        stock_ids = stocks_df["stock_id"].tolist()
        total = len(stock_ids)
        
        start_idx = self.meta.get("update_progress", 0)
        if start_idx > 0:
            print(f"  🔄 斷點續傳: 從序號 {start_idx + 1}/{total} 繼續")

        print(f"  📊 更新 {total} 檔股票")

        all_price, all_inst, all_margin, all_per, all_rev, all_fin = [], [], [], [], [], []

        for i in range(start_idx, total):
            sid = stock_ids[i]
            print(f"\r  [{i + 1}/{total}] {sid}...", end="", flush=True)

            try:
                df = self.fetcher.get_daily_price(sid, start_date, end_date)
                if df is not None and len(df) > 0:
                    all_price.append(df)
            except Exception as e:
                if self._is_quota_error(e):
                    print(f"\n🛑 [STOP] API 額度已耗盡。已儲存目前進度 (序號 {i})，請一小時後再試。")
                    self.meta["update_progress"] = i
                    self._save_meta()
                    return False
            time.sleep(self.api_delay)

            try:
                df = self.fetcher.get_institutional(sid, start_date, end_date)
                if df is not None and len(df) > 0:
                    all_inst.append(df)
            except Exception as e:
                if self._is_quota_error(e):
                    print(f"\n🛑 [STOP] API 額度已耗盡。")
                    self.meta["update_progress"] = i
                    self._save_meta()
                    return False
            time.sleep(self.api_delay)

            try:
                df = self.fetcher.get_margin(sid, start_date, end_date)
                if df is not None and len(df) > 0:
                    all_margin.append(df)
            except Exception as e:
                if self._is_quota_error(e):
                    print(f"\n🛑 [STOP] API 額度已耗盡。")
                    self.meta["update_progress"] = i
                    self._save_meta()
                    return False
            time.sleep(self.api_delay)

            try:
                df = self.fetcher.get_per_pbr(sid, start_date, end_date)
                if df is not None and len(df) > 0:
                    all_per.append(df)
            except Exception:
                pass
            time.sleep(self.api_delay)

            try:
                df = self.fetcher.get_revenue(sid, start_date, end_date)
                if df is not None and len(df) > 0:
                    all_rev.append(df)
            except Exception:
                pass
            time.sleep(self.api_delay)

            try:
                df = self.fetcher.get_financial(sid, start_date, end_date)
                if df is not None and len(df) > 0:
                    all_fin.append(df)
            except Exception:
                pass
            time.sleep(self.api_delay)

            # 每 100 檔存一次
            if (i + 1) % 100 == 0:
                self._save_batch(all_price, all_inst, all_margin, all_per, all_rev, all_fin)
                all_price, all_inst, all_margin, all_per, all_rev, all_fin = [], [], [], [], [], []
                self.meta["update_progress"] = i + 1
                self._save_meta()
                print(f"\n    💾 已儲存至序號 {i + 1}")
                if i < total - 1:
                    print(f"    💤 暫停 {self.batch_delay}s (API 限速)...")
                    time.sleep(self.batch_delay)

        # 最後一批
        self._save_batch(all_price, all_inst, all_margin, all_per, all_rev, all_fin)

        self.meta["last_update"] = end_date
        self.meta["last_price_date"] = end_date
        self.meta["last_institutional_date"] = end_date
        self.meta["last_margin_date"] = end_date
        self.meta["last_per_date"] = end_date
        self.meta["last_revenue_date"] = end_date
        self.meta["last_financial_date"] = end_date
        self.meta["update_progress"] = 0 # reset
        self._save_meta()

        print(f"\n\n  ✅ 增量更新完成！")
        self._print_cache_status()
        return True

    def _save_batch(self, all_price, all_inst, all_margin, all_per, all_rev, all_fin):
        """輔助方法: 儲存更新批次"""
        for df in all_price: self._save_to_stock_folder(df["stock_id"].iloc[0], "price.csv", df)
        for df in all_inst: self._save_to_stock_folder(df["stock_id"].iloc[0], "institutional.csv", df)
        for df in all_margin: self._save_to_stock_folder(df["stock_id"].iloc[0], "margin.csv", df)
        for df in all_per: self._save_to_stock_folder(df["stock_id"].iloc[0], "per_pbr.csv", df)
        for df in all_rev: self._save_to_stock_folder(df["stock_id"].iloc[0], "revenue.csv", df)
        for df in all_fin: self._save_to_stock_folder(df["stock_id"].iloc[0], "financial.csv", df)

    # ─── 讀取本地資料 ───────────────────────────────────────────

    def preload_all_data(self):
        """一次載入所有資料到記憶體，以利快速全市場分析"""
        print("  ⏳ 正在快取資料到緩衝區 (加速讀取)...")
        self._memory_cache["daily_price"] = self._load_all_stocks_folder("price.csv")
        self._memory_cache["institutional"] = self._load_all_stocks_folder("institutional.csv")
        self._memory_cache["margin"] = self._load_all_stocks_folder("margin.csv")
        self._memory_cache["per_pbr"] = self._load_all_stocks_folder("per_pbr.csv")
        self._memory_cache["revenue"] = self._load_all_stocks_folder("revenue.csv")
        self._memory_cache["financial"] = self._load_all_stocks_folder("financial.csv")

        print("  ✅ 記憶體快取完成！")

    def _load_all_stocks_folder(self, target_filename: str) -> dict:
        """從各股票資料夾平行載入並組合"""
        out = {}
        if not os.path.exists(CACHE_DIR):
            return out
        
        for sid in os.listdir(CACHE_DIR):
            path = os.path.join(CACHE_DIR, sid, target_filename)
            if os.path.exists(path) and sid.isdigit():
                df = self._load_csv_path(path)
                if not df.empty:
                    out[sid] = df
        return out


    def _get_from_memory_or_disk(self, cache_key: str, filename: str, stock_id: str = None) -> pd.DataFrame:
        """從記憶庫取得，若沒有則從硬碟讀單筆（向下相容）"""
        mem_cache = self._memory_cache.get(cache_key)
        
        if mem_cache is not None:
            # 已經 preload
            if stock_id:
                # groupby 分出來的 df 可以直接回傳，防呆轉發空的 df
                return mem_cache.get(stock_id, pd.DataFrame())
            else:
                # 要全部資料 (這通常不會發生，只有 load_institutional_all 會要)
                # 若需要全部，把所有 value concat 起來
                if mem_cache:
                    return pd.concat(mem_cache.values(), ignore_index=True)
                return pd.DataFrame()
        else:
            # 未 preload，走傳統讀檔
            return self._load_csv(filename, stock_id)

    def load_price(self, stock_id: str = None) -> pd.DataFrame:
        return self._get_from_memory_or_disk("daily_price", "price.csv", stock_id)

    def load_institutional(self, stock_id: str = None) -> pd.DataFrame:
        return self._get_from_memory_or_disk("institutional", "institutional.csv", stock_id)

    def load_institutional_all(self) -> pd.DataFrame:
        """讀取全市場三大法人快取 (族群輪動用)"""
        mem = self._memory_cache.get("institutional")
        if mem is not None:
             if mem: return pd.concat(mem.values(), ignore_index=True)
             return pd.DataFrame()
        # 傳統備案，從所有 stock_data 當中搜括
        all_inst = self._load_all_stocks_folder("institutional.csv")
        if all_inst: return pd.concat(all_inst.values(), ignore_index=True)
        return pd.DataFrame()

    def load_margin(self, stock_id: str = None) -> pd.DataFrame:
        return self._get_from_memory_or_disk("margin", "margin.csv", stock_id)

    def load_per(self, stock_id: str = None) -> pd.DataFrame:
        return self._get_from_memory_or_disk("per_pbr", "per_pbr.csv", stock_id)

    def load_revenue(self, stock_id: str = None) -> pd.DataFrame:
        return self._get_from_memory_or_disk("revenue", "revenue.csv", stock_id)

    def load_financial(self, stock_id: str = None) -> pd.DataFrame:
        return self._get_from_memory_or_disk("financial", "financial.csv", stock_id)

    def _load_csv_path(self, path: str) -> pd.DataFrame:
        """從指定路徑載入 CSV 並處理日期"""
        if not os.path.exists(path):
            return pd.DataFrame()
        df = pd.read_csv(path, low_memory=False, dtype={"stock_id": str})
        if "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"].astype(str).str[:10], errors="coerce")
        return df


    def load_stock_info(self) -> pd.DataFrame:
        """讀取股票總覽"""
        path = os.path.join(CACHE_DIR, "stock_info.csv")
        if os.path.exists(path):
            return pd.read_csv(path)
        return self.fetcher.get_stock_info()

    def get_all_stock_ids(self) -> list:
        """取得快取中的所有股票代碼"""
        info = self.load_stock_info()
        listed = info[info["type"].isin(["twse", "tpex"])]
        etf_keywords = ["ETF", "上櫃ETF", "ETN"]
        listed = listed[~listed["industry_category"].isin(etf_keywords)]
        listed = listed[listed["stock_id"].str.match(r"^\d{4}$")]
        return listed["stock_id"].tolist()

    def get_cached_stock_ids(self) -> list:
        """取得目前本地已下載資料的股票代碼"""
        cached_ids = set()
        if os.path.exists(CACHE_DIR):
            for d in os.listdir(CACHE_DIR):
                if os.path.isdir(os.path.join(CACHE_DIR, d)) and d.isdigit():
                    cached_ids.add(d)
        return sorted(list(cached_ids))

    def download_deep_fundamental(self, stock_id: str):
        """下載特定股票 5 年份的基本面資料"""
        rev_dir = os.path.join(CACHE_DIR, stock_id)
        os.makedirs(rev_dir, exist_ok=True)
        
        path_rev = os.path.join(rev_dir, "revenue.csv")
        path_fin = os.path.join(rev_dir, "financial.csv")

        # 檢查是否已存在且檔案不為空 (大於 100 bytes)
        if os.path.exists(path_rev) and os.path.exists(path_fin):
            if os.path.getsize(path_rev) > 100 and os.path.getsize(path_fin) > 100:
                print(f"  ✨ {stock_id} 資料已存在，跳過重複下載。")
                return {"status": "already_existed", "path": rev_dir, "revenue": True, "financial": True}

        # 5 年約 1825 天
        start_date = (datetime.now() - timedelta(days=1825)).strftime("%Y-%m-%d")
        end_date = datetime.now().strftime("%Y-%m-%d")
        
        print(f"  📥 下載 {stock_id} 五年基本面資料...")
        
        results = {"status": "downloaded", "revenue": False, "financial": False, "path": rev_dir}
        
        # 營收
        try:
            df_rev = self.fetcher.get_revenue(stock_id, start_date, end_date)
            if df_rev is not None and not df_rev.empty:
                df_rev.to_csv(path_rev, index=False, encoding="utf-8-sig")
                results["revenue"] = True
        except Exception as e:
            print(f"  ⚠️ {stock_id} 營收下載失敗: {e}")
        
        time.sleep(self.api_delay)
            
        # 財報
        try:
            df_fin = self.fetcher.get_financial(stock_id, start_date, end_date)
            if df_fin is not None and not df_fin.empty:
                df_fin.to_csv(os.path.join(rev_dir, "financial.csv"), index=False, encoding="utf-8-sig")
                results["financial"] = True
        except Exception as e:
            print(f"  ⚠️ {stock_id} 財報下載失敗: {e}")
        
        time.sleep(self.api_delay)
            
        return results

    def update_single_stock_cache(self, stock_id: str):
        """下載並更新單一股票的所有快取資料 (用於補齊缺失資料)"""
        print(f"  ⚡ 偵測到 {stock_id} 缺失，啟動即時下載補強...")
        
        # 準備區間
        start_date = (datetime.now() - timedelta(days=180)).strftime("%Y-%m-%d")
        start_date_rev = (datetime.now() - timedelta(days=400)).strftime("%Y-%m-%d")
        end_date = datetime.now().strftime("%Y-%m-%d")
        
        try:
            # 1-4 如舊 (暫留在大檔，或未來也可分拆)
            # ... (price, inst, margin, per) ...
            df_price = self.fetcher.get_daily_price(stock_id, start_date, end_date)
            if df_price is not None and not df_price.empty:
                self._save_to_stock_folder(stock_id, "price.csv", df_price)
            time.sleep(self.api_delay)
            
            df_inst = self.fetcher.get_institutional(stock_id, start_date, end_date)
            if df_inst is not None and not df_inst.empty:
                self._save_to_stock_folder(stock_id, "institutional.csv", df_inst)
            time.sleep(self.api_delay)
                
            df_margin = self.fetcher.get_margin(stock_id, start_date, end_date)
            if df_margin is not None and not df_margin.empty:
                self._save_to_stock_folder(stock_id, "margin.csv", df_margin)
            time.sleep(self.api_delay)
                
            df_per = self.fetcher.get_per_pbr(stock_id, start_date, end_date)
            if df_per is not None and not df_per.empty:
                self._save_to_stock_folder(stock_id, "per_pbr.csv", df_per)
            time.sleep(self.api_delay)
                
            df_rev = self.fetcher.get_revenue(stock_id, start_date_rev, end_date)
            if df_rev is not None and not df_rev.empty:
                self._save_to_stock_folder(stock_id, "revenue.csv", df_rev)
            time.sleep(self.api_delay)
            
            df_fin = self.fetcher.get_financial(stock_id, start_date_rev, end_date)
            if df_fin is not None and not df_fin.empty:
                self._save_to_stock_folder(stock_id, "financial.csv", df_fin)
            time.sleep(self.api_delay)
                
            print(f"  ✅ {stock_id} 即時快取更新完成 (基本面已分類至 revenue 目錄)")
            return True

        except Exception as e:
            if self._is_quota_error(e):
                print(f"  ❌ {stock_id} 即時更新失敗: API 額度用完，請稍後再試。")
            else:
                print(f"  ❌ {stock_id} 即時快取更新失敗: {e}")
            return False


    def _save_to_stock_folder(self, stock_id, filename, df):
        """通用儲存到獨立股票目錄"""
        stock_dir = os.path.join(CACHE_DIR, str(stock_id))
        os.makedirs(stock_dir, exist_ok=True)
        path = os.path.join(stock_dir, filename)
        self._append_or_create_csv(path, df)



    def _append_or_create_csv(self, path, df):
        """通用: 追加或建立 CSV 且去重"""
        if os.path.exists(path):
            existing = pd.read_csv(path, low_memory=False, dtype={"stock_id": str})
            # 合併
            combined = pd.concat([existing, df], ignore_index=True)
            # 去重
            if "date" in combined.columns:
                 # 同時考慮 stock_id 以防萬一，雖然目前路徑已分開
                 subset = ["date", "stock_id"] if "stock_id" in combined.columns else ["date"]
                 combined = combined.drop_duplicates(subset=subset, keep="last")
            combined.to_csv(path, index=False, encoding="utf-8-sig")
        else:
            df.to_csv(path, index=False, encoding="utf-8-sig")

    def _is_quota_error(self, e: Exception) -> bool:
        """判斷是否為 API 額度用完的錯誤"""
        msg = str(e).lower()
        # FinMind 常見錯誤訊息或 'data' KeyError (代表 API 回傳結構不完整)
        return "'data'" in msg or "quota" in msg or "rate limit" in msg or "429" in msg or "403" in msg

    # ─── 工具方法 ───────────────────────────────────────────────


    def _load_csv(self, filename: str, stock_id: str = None) -> pd.DataFrame:
        if stock_id:
            path = os.path.join(CACHE_DIR, str(stock_id), filename)
        else:
            path = os.path.join(CACHE_DIR, filename)

        if not os.path.exists(path):
            return pd.DataFrame()
        df = pd.read_csv(path, low_memory=False, dtype={"stock_id": str})
        if "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"].astype(str).str[:10], errors="coerce")
        return df

    def _print_cache_status(self):
        """顯示快取狀態"""
        print(f"\n  📁 快取目錄: {CACHE_DIR}")
        print(f"  📅 最後更新: {self.meta.get('last_update', 'N/A')}")
        print(f"  📊 股票數量: {self.meta.get('stock_count', 0)}")
        for fname in ["stock_info.csv", "daily_price.csv", "institutional.csv", "margin.csv", "per_pbr.csv"]:
            path = os.path.join(CACHE_DIR, fname)
            if os.path.exists(path):
                size_mb = os.path.getsize(path) / 1024 / 1024
                print(f"     {fname}: {size_mb:.1f} MB")



    def get_last_update(self) -> str:
        return self.meta.get("last_update", "N/A")

    def is_initialized(self) -> bool:
        return self.meta.get("initialized", False)
