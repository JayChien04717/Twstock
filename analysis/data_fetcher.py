"""
AI 台股分析師 — FinMind 資料擷取模組
當 FinMind API 額度用完時，自動 fallback 到 yfinance 下載日K線。
"""
import pandas as pd
from datetime import datetime, timedelta
from FinMind.data import DataLoader

from config import FINMIND_API_TOKEN


def _is_quota_error(e: Exception) -> bool:
    """判斷是否為 API 額度用完的錯誤"""
    msg = str(e).lower()
    return "'data'" in msg or "quota" in msg or "rate limit" in msg or "429" in msg or "403" in msg


def _yfinance_daily_price(stock_id: str, start_date: str, end_date: str = None) -> pd.DataFrame:
    """
    用 yfinance 下載台股日K線，回傳與 FinMind 格式一致的 DataFrame。
    台灣上市 → {id}.TW，上櫃 → {id}.TWO (先試 .TW，再試 .TWO)
    """
    try:
        import yfinance as yf
    except ImportError:
        print("⚠️  yfinance 未安裝，請執行: pip install yfinance")
        return pd.DataFrame()

    end = end_date or datetime.now().strftime("%Y-%m-%d")

    for suffix in [".TW", ".TWO"]:
        ticker = f"{stock_id}{suffix}"
        try:
            df = yf.download(
                ticker,
                start=start_date,
                end=end,
                auto_adjust=True,
                progress=False,
                show_errors=False,
            )
            if df is None or df.empty:
                continue

            # 展平 MultiIndex columns (yfinance >= 0.2 可能產生)
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)

            df = df.reset_index()
            df = df.rename(
                columns={
                    "Date": "date",
                    "Open": "open",
                    "High": "high",
                    "Low": "low",
                    "Close": "close",
                    "Volume": "Trading_Volume",
                }
            )
            df["date"] = pd.to_datetime(df["date"].astype(str).str[:10], errors="coerce")
            df["stock_id"] = stock_id

            # 台灣股市成交金額 (yfinance 無此欄，補 0)
            if "Trading_money" not in df.columns:
                df["Trading_money"] = 0
            if "Trading_turnover" not in df.columns:
                df["Trading_turnover"] = 0
            if "spread" not in df.columns:
                df["spread"] = 0

            # 保留標準欄位
            keep = ["stock_id", "date", "open", "high", "low", "close", "Trading_Volume",
                    "Trading_money", "Trading_turnover", "spread"]
            df = df[[c for c in keep if c in df.columns]]
            return df
        except Exception:
            continue

    return pd.DataFrame()


class StockDataFetcher:
    """封裝 FinMind API 的資料擷取器，額度不足時自動 fallback 到 yfinance"""

    def __init__(self, token: str = None, use_yfinance: bool = False):
        """
        use_yfinance: True → 強制使用 yfinance (跳過 FinMind)，適合 token 已耗盡時。
        """
        self.api = DataLoader()
        self.api.login_by_token(api_token=token or FINMIND_API_TOKEN)
        self._stock_info_cache = None
        self.use_yfinance = use_yfinance
        # 記錄本次執行是否已偵測到 FinMind 額度耗盡，之後直接走 yfinance
        self._quota_exhausted = use_yfinance

    # ─── 股票基本資訊 ───────────────────────────────────────────

    def get_stock_info(self) -> pd.DataFrame:
        """取得所有上市櫃股票資訊 (含產業別)"""
        import time
        if self._stock_info_cache is None:
            empty_info = pd.DataFrame(columns=["stock_id", "stock_name", "type", "industry_category"])

            for i in range(3):
                try:
                    self._stock_info_cache = self.api.taiwan_stock_info()
                    if self._stock_info_cache is not None and not self._stock_info_cache.empty:
                        break
                except Exception as e:
                    if i == 2:
                        print(f"❌ 無法取得股票資訊: {e}")
                        self._stock_info_cache = empty_info
                        return empty_info
                    print(f"⚠️ 取得股票資訊失敗 (第 {i+1} 次)，正在重試...")
                    time.sleep(2)

            if self._stock_info_cache is None or self._stock_info_cache.empty:
                self._stock_info_cache = empty_info
                return empty_info

        return self._stock_info_cache

    def get_stock_name(self, stock_id: str) -> str:
        """取得股票名稱"""
        info = self.get_stock_info()
        if info is None or info.empty or "stock_id" not in info.columns:
            return stock_id
        row = info[info["stock_id"] == stock_id]
        if len(row) > 0:
            return row.iloc[0]["stock_name"]
        return stock_id

    def get_industry(self, stock_id: str) -> str:
        """取得股票產業別"""
        info = self.get_stock_info()
        if info is None or info.empty or "stock_id" not in info.columns:
            return "未知"
        row = info[info["stock_id"] == stock_id]
        if len(row) > 0:
            return row.iloc[0]["industry_category"]
        return "未知"

    # ─── 技術面資料 ─────────────────────────────────────────────

    def get_daily_price(
        self, stock_id: str, start_date: str, end_date: str = None
    ) -> pd.DataFrame:
        """
        取得日 K 線 (OHLCV)。
        優先使用 FinMind；若額度不足(或 use_yfinance=True)，自動切換 yfinance。
        """
        # 若已知額度耗盡，直接用 yfinance
        if self._quota_exhausted:
            return _yfinance_daily_price(stock_id, start_date, end_date)

        try:
            params = {"stock_id": stock_id, "start_date": start_date}
            if end_date:
                params["end_date"] = end_date
            df = self.api.taiwan_stock_daily(**params)
            if len(df) > 0:
                df["date"] = pd.to_datetime(df["date"].astype(str).str[:10], errors="coerce")
                rename_map = {}
                if "max" in df.columns:
                    rename_map["max"] = "high"
                if "min" in df.columns:
                    rename_map["min"] = "low"
                if rename_map:
                    df = df.rename(columns=rename_map)
            return df

        except Exception as e:
            if _is_quota_error(e):
                print(f"\n⚠️  FinMind 額度用完，自動切換 yfinance 下載 {stock_id}...")
                self._quota_exhausted = True
                return _yfinance_daily_price(stock_id, start_date, end_date)
            raise  # 非額度錯誤，繼續往上拋

    def get_per_pbr(
        self, stock_id: str, start_date: str, end_date: str = None
    ) -> pd.DataFrame:
        """取得 PER / PBR 資料 (僅 FinMind；yfinance 不提供此欄位)"""
        if self._quota_exhausted:
            return pd.DataFrame()
        params = {"stock_id": stock_id, "start_date": start_date}
        if end_date:
            params["end_date"] = end_date
        df = self.api.taiwan_stock_per_pbr(**params)
        if len(df) > 0:
            df["date"] = pd.to_datetime(df["date"].astype(str).str[:10], errors="coerce")
        return df

    # ─── 籌碼面資料 ─────────────────────────────────────────────

    def get_institutional(
        self, stock_id: str, start_date: str, end_date: str = None
    ) -> pd.DataFrame:
        """取得三大法人買賣超 (僅 FinMind；yfinance 不提供)"""
        if self._quota_exhausted:
            return pd.DataFrame()
        params = {"stock_id": stock_id, "start_date": start_date}
        if end_date:
            params["end_date"] = end_date
        df = self.api.taiwan_stock_institutional_investors(**params)
        if len(df) > 0:
            df["date"] = pd.to_datetime(df["date"].astype(str).str[:10], errors="coerce")
        return df

    def get_institutional_all(
        self, start_date: str, end_date: str = None
    ) -> pd.DataFrame:
        """取得所有股票的三大法人買賣超 (用於族群輪動分析)"""
        if self._quota_exhausted:
            return pd.DataFrame()
        import requests

        url = "https://api.finmindtrade.com/api/v4/data"
        headers = {"Authorization": f"Bearer {FINMIND_API_TOKEN}"}
        params = {
            "dataset": "TaiwanStockInstitutionalInvestorsBuySell",
            "start_date": start_date,
        }
        if end_date:
            params["end_date"] = end_date
        resp = requests.get(url, headers=headers, params=params)
        data = resp.json()
        if data.get("data"):
            df = pd.DataFrame(data["data"])
            if len(df) > 0:
                df["date"] = pd.to_datetime(df["date"].astype(str).str[:10], errors="coerce")
            return df
        return pd.DataFrame()

    def get_margin(
        self, stock_id: str, start_date: str, end_date: str = None
    ) -> pd.DataFrame:
        """取得融資融券資料 (僅 FinMind；yfinance 不提供)"""
        if self._quota_exhausted:
            return pd.DataFrame()
        params = {"stock_id": stock_id, "start_date": start_date}
        if end_date:
            params["end_date"] = end_date
        df = self.api.taiwan_stock_margin_purchase_short_sale(**params)
        if len(df) > 0:
            df["date"] = pd.to_datetime(df["date"].astype(str).str[:10], errors="coerce")
        return df

    # ─── 基本面資料 ─────────────────────────────────────────────

    def get_revenue(
        self, stock_id: str, start_date: str, end_date: str = None
    ) -> pd.DataFrame:
        """取得月營收 (僅 FinMind；yfinance 不提供)"""
        if self._quota_exhausted:
            return pd.DataFrame()
        params = {"stock_id": stock_id, "start_date": start_date}
        if end_date:
            params["end_date"] = end_date
        df = self.api.taiwan_stock_month_revenue(**params)
        if len(df) > 0:
            df["date"] = pd.to_datetime(df["date"].astype(str).str[:10], errors="coerce")
        return df

    def get_financial(
        self, stock_id: str, start_date: str, end_date: str = None
    ) -> pd.DataFrame:
        """取得綜合損益表 (僅 FinMind；yfinance 不提供)"""
        if self._quota_exhausted:
            return pd.DataFrame()
        params = {"stock_id": stock_id, "start_date": start_date}
        if end_date:
            params["end_date"] = end_date
        df = self.api.taiwan_stock_financial_statement(**params)
        if len(df) > 0:
            df["date"] = pd.to_datetime(df["date"].astype(str).str[:10], errors="coerce")
        return df

    # ─── 批次擷取工具 ───────────────────────────────────────────

    def get_multi_daily_price(
        self, stock_ids: list, start_date: str, end_date: str = None
    ) -> dict:
        """批次取得多檔股票日 K 線"""
        result = {}
        for sid in stock_ids:
            try:
                result[sid] = self.get_daily_price(sid, start_date, end_date)
            except Exception as e:
                print(f"[WARN] 無法取得 {sid} 股價: {e}")
        return result

    def get_lookback_date(self, days: int = 90) -> str:
        """計算往回推的起始日期"""
        return (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

    def get_today(self) -> str:
        """取得今天日期"""
        return datetime.now().strftime("%Y-%m-%d")
