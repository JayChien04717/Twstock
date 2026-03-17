"""
AI 台股分析師 — 主引擎 (整合所有模組)
"""
import sys
from datetime import datetime, timedelta

from data_fetcher import StockDataFetcher
from technical_analysis import TechnicalAnalysis
from chip_analysis import ChipAnalysis
from fundamental_analysis import FundamentalAnalysis
from sector_rotation import SectorRotation
from stock_selector import StockSelector
from report_generator import ReportGenerator
from config import DEFAULT_WATCHLIST


class AIAnalyst:
    """AI 分析師：整合全部分析模組"""

    def __init__(self, watchlist: list = None):
        self.watchlist = watchlist or DEFAULT_WATCHLIST
        self.fetcher = StockDataFetcher()
        self.tech = TechnicalAnalysis()
        self.chip = ChipAnalysis()
        self.fund = FundamentalAnalysis()
        self.selector = StockSelector()
        self.reporter = ReportGenerator()
        self._stock_info = None

    # ─── 原版: 從 API 即時分析 (自訂清單) ───────────────────────

    def run_daily_analysis(self, target_date: str = None) -> dict:
        """
        執行每日完整分析 (從 API 即時抓取)
        target_date: 分析日期 (預設今天), 格式 YYYY-MM-DD
        """
        if target_date is None:
            target_date = self.fetcher.get_today()

        print(f"\n{'='*60}")
        print(f"  🤖 AI 台股分析師 — 每日分析啟動")
        print(f"  📅 分析日期: {target_date}")
        print(f"  📋 追蹤清單: {len(self.watchlist)} 檔股票")
        print(f"{'='*60}\n")

        # Step 1: 取得股票基本資訊
        print("📂 [1/6] 載入股票基本資訊...")
        self._stock_info = self.fetcher.get_stock_info()
        print(f"   已載入 {len(self._stock_info)} 檔股票資訊")

        # Step 2: 分析各股
        print(f"\n📈 [2/6] 分析個股 ({len(self.watchlist)} 檔)...")
        lookback = self.fetcher.get_lookback_date(days=180)
        lookback_short = self.fetcher.get_lookback_date(days=30)
        lookback_revenue = self.fetcher.get_lookback_date(days=400)

        stock_analyses = {}
        for i, stock_id in enumerate(self.watchlist, 1):
            name = self.fetcher.get_stock_name(stock_id)
            sys.stdout.write(f"\r   [{i}/{len(self.watchlist)}] {stock_id} {name}...")
            sys.stdout.flush()

            try:
                analysis = self._analyze_single_stock(
                    stock_id, lookback, lookback_short, lookback_revenue, target_date
                )
                analysis["name"] = name
                stock_analyses[stock_id] = analysis
            except Exception as e:
                print(f"\n   ⚠️ {stock_id} 分析失敗: {e}")

        print(f"\n   ✅ 完成 {len(stock_analyses)} 檔股票分析")

        # Step 3-6: 排名、輪動、報告
        return self._finalize_report(target_date, stock_analyses, lookback_short)

    # ─── 全市場掃描: 從 Cache 分析 ──────────────────────────────

    def run_full_market_scan(self, target_date: str = None) -> dict:
        """
        全市場掃描: 從 Stock_base_data 本地快取分析所有股票
        需要先執行 --init-cache 建立快取
        """
        from stock_cache import StockCache

        cache = StockCache()
        if not cache.is_initialized():
            print("❌ 快取尚未初始化！請先執行:")
            print("   python main.py --init-cache")
            return {}

        if target_date is None:
            target_date = self.fetcher.get_today()

        print(f"\n{'='*60}")
        print(f"  🤖 AI 台股分析師 — 全市場掃描模式")
        print(f"  📅 分析日期: {target_date}")
        print(f"  📦 資料來源: Stock_base_data (快取: {cache.get_last_update()})")
        print(f"{'='*60}\n")

        # Step 1: 從快取載入股票資訊與預載全市場資料
        print("📂 [1/6] 從快取載入資料...")
        self._stock_info = cache.load_stock_info()
        all_stock_ids = cache.get_all_stock_ids()
        total = len(all_stock_ids)
        print(f"   共 {total} 檔股票")
        
        # 預載全部 CSV 到記憶體以加速分析
        cache.preload_all_data()

        # Step 2: 從記憶體分析每檔股票
        print(f"\n📈 [2/6] 從快取分析 {total} 檔股票...")
        stock_analyses = {}
        success = 0

        for i, stock_id in enumerate(all_stock_ids, 1):
            if i % 100 == 0 or i == total:
                sys.stdout.write(f"\r   [{i}/{total}] 分析中...")
                sys.stdout.flush()

            try:
                # 全市場掃描不應觸發即時補抓，由背景執行緒補齊
                analysis = self._analyze_from_cache(cache, stock_id, allow_update=False)
                if analysis:
                    # 取得股票名稱
                    info_row = self._stock_info[self._stock_info["stock_id"] == stock_id]
                    name = info_row.iloc[0]["stock_name"] if len(info_row) > 0 else stock_id
                    analysis["name"] = name
                    stock_analyses[stock_id] = analysis
                    success += 1
            except Exception:
                pass

        print(f"\n   ✅ 成功分析 {success}/{total} 檔股票")

        # Step 3: 族群輪動 (全市場法人資料)
        print(f"\n🔄 [3/6] 全市場族群資金輪動分析...")
        inst_all_df = cache.load_institutional_all()
        if len(inst_all_df) > 0:
            rotation = SectorRotation(self._stock_info)
            sector_result = rotation.analyze(inst_all_df, days_list=[1, 3, 5])
            summary = sector_result.get("summary", {})
            print(f"   趨勢: {summary.get('rotation', 'N/A')}")
        else:
            sector_result = {"error": "無法人資料", "summary": {"details": [], "rotation": "無資料"}}

        # Step 4-6: 排名、報告
        return self._finalize_report(target_date, stock_analyses, sector_result=sector_result)

    def _analyze_from_cache(self, cache, stock_id: str, allow_update: bool = True) -> dict:
        """從本地快取分析單一股票"""
        # 技術面
        price_df = cache.load_price(stock_id)
        
        # 如果沒資料，嘗試即時抓取一次並更新快取
        if (price_df is None or price_df.empty) and allow_update:
            if cache.update_single_stock_cache(stock_id):
                price_df = cache.load_price(stock_id)
        
        tech_result = self.tech.analyze(price_df)

        # 籌碼面
        inst_df = cache.load_institutional(stock_id)
        margin_df = cache.load_margin(stock_id)
        chip_result = self.chip.analyze(inst_df, margin_df)

        # 基本面 (營收、估值、財報)
        per_df = cache.load_per(stock_id)
        rev_df = cache.load_revenue(stock_id)
        fin_df = cache.load_financial(stock_id)
        fund_result = self.fund.analyze(rev_df, per_df, fin_df)

        # 如果三個都沒資料就跳過
        if tech_result.get("error") and chip_result.get("institutional", {}).get("error"):
            return None

        return {
            "technical": tech_result,
            "chip": chip_result,
            "fundamental": fund_result,
        }

    # ─── 共用: 產出報告 ─────────────────────────────────────────

    def _finalize_report(
        self, target_date, stock_analyses, lookback_short=None, sector_result=None
    ) -> dict:
        """共用的排名 + 輪動 + 報告"""
        # 選股排名
        print(f"\n🎯 [4/6] 選股引擎評分排名...")
        ranked = self.selector.rank(stock_analyses)
        top_picks = self.selector.top_picks(ranked)
        risk_alerts = self.selector.risk_alerts(ranked)
        if top_picks:
            print(f"   Top 1: {top_picks[0]['stock_id']} {top_picks[0]['name']} ({top_picks[0]['stars']})")

        # 族群輪動 (如果還沒做)
        if sector_result is None:
            print(f"\n🔄 [5/6] 族群資金輪動分析...")
            sector_result = self._analyze_sector_rotation(lookback_short, target_date)
            summary = sector_result.get("summary", {})
            print(f"   趨勢: {summary.get('rotation', '分析中...')}")
        else:
            print(f"\n🔄 [5/6] 族群輪動 (已完成)")

        # 產出報告
        print(f"\n📝 [6/6] 產出分析報告...")
        text_report = self.reporter.generate_text_report(
            date=target_date,
            top_picks=top_picks,
            sector_rotation=sector_result,
            risk_alerts=risk_alerts,
        )

        html_data = self.reporter.generate_html_data(
            date=target_date,
            ranked_stocks=ranked,
            sector_rotation=sector_result,
            stock_analyses=stock_analyses,
        )

        print(f"   ✅ 報告產出完成")
        print(f"\n📤 完成！")
        print(text_report)

        return {
            "date": target_date,
            "text_report": text_report,
            "html_data": html_data,
            "ranked": ranked,
            "sector_rotation": sector_result,
            "stock_analyses": stock_analyses,
            "risk_alerts": risk_alerts,
        }

    # ─── 單股分析 (API) ─────────────────────────────────────────

    def _analyze_single_stock(
        self,
        stock_id: str,
        lookback: str,
        lookback_short: str,
        lookback_revenue: str,
        target_date: str,
    ) -> dict:
        """分析單一股票 (從 API)"""
        # 技術面
        price_df = self.fetcher.get_daily_price(stock_id, lookback, target_date)
        tech_result = self.tech.analyze(price_df)

        # 籌碼面
        inst_df = self.fetcher.get_institutional(stock_id, lookback_short, target_date)
        margin_df = self.fetcher.get_margin(stock_id, lookback_short, target_date)
        chip_result = self.chip.analyze(inst_df, margin_df)

        # 基本面
        try:
            rev_df = self.fetcher.get_revenue(stock_id, lookback_revenue, target_date)
        except Exception:
            rev_df = None
        try:
            per_df = self.fetcher.get_per_pbr(stock_id, lookback, target_date)
        except Exception:
            per_df = None
        try:
            fin_df = self.fetcher.get_financial(stock_id, lookback_revenue, target_date)
        except Exception:
            fin_df = None

        fund_result = self.fund.analyze(rev_df, per_df, fin_df)

        return {
            "technical": tech_result,
            "chip": chip_result,
            "fundamental": fund_result,
        }

    def _analyze_sector_rotation(self, start_date: str, end_date: str) -> dict:
        """族群資金輪動分析 (從 API)"""
        try:
            inst_all_df = self.fetcher.get_institutional_all(start_date, end_date)
            rotation = SectorRotation(self._stock_info)
            return rotation.analyze(inst_all_df, days_list=[1, 3, 5])
        except Exception as e:
            print(f"   ⚠️ 族群輪動分析失敗: {e}")
            return {"error": str(e), "summary": {"details": [], "rotation": "分析失敗"}}

    def analyze_stock(self, stock_id: str, target_date: str = None) -> dict:
        """分析單一指定股票 (輕量版，直接從本地快取讀取)"""
        if target_date is None:
            target_date = self.fetcher.get_today()

        from stock_cache import StockCache
        cache = StockCache()
        
        name = self.fetcher.get_stock_name(stock_id)
        analysis = self._analyze_from_cache(cache, stock_id)
        
        if not analysis:
            return {"error": f"資料庫中無 {stock_id} 資訊，可能非上市櫃或無快取資料", "name": name}

        analysis["name"] = name
        return analysis

