"""
AI 台股分析師 — FinMind 資料擷取模組
"""
import pandas as pd
from datetime import datetime, timedelta
from FinMind.data import DataLoader

from config import FINMIND_API_TOKEN


class StockDataFetcher:
    """封裝 FinMind API 的資料擷取器"""

    def __init__(self, token: str = None):
        self.api = DataLoader()
        self.api.login_by_token(api_token=token or FINMIND_API_TOKEN)
        self._stock_info_cache = None

    # ─── 股票基本資訊 ───────────────────────────────────────────

    def get_stock_info(self) -> pd.DataFrame:
        """取得所有上市櫃股票資訊 (含產業別)"""
        import time
        if self._stock_info_cache is None:
            # 建立空的但有欄位的 DataFrame 作為預設
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
        """取得日 K 線 (OHLCV)"""
        params = {"stock_id": stock_id, "start_date": start_date}
        if end_date:
            params["end_date"] = end_date
        df = self.api.taiwan_stock_daily(**params)
        if len(df) > 0:
            df["date"] = pd.to_datetime(df["date"].astype(str).str[:10], errors="coerce")
            # FinMind 用 max/min，統一改為 high/low
            rename_map = {}
            if "max" in df.columns:
                rename_map["max"] = "high"
            if "min" in df.columns:
                rename_map["min"] = "low"
            if rename_map:
                df = df.rename(columns=rename_map)
        return df

    def get_per_pbr(
        self, stock_id: str, start_date: str, end_date: str = None
    ) -> pd.DataFrame:
        """取得 PER / PBR 資料"""
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
        """取得三大法人買賣超"""
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
        """取得融資融券資料"""
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
        """取得月營收"""
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
        """取得綜合損益表"""
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
