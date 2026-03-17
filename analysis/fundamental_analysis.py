"""
AI 台股分析師 — 基本面分析模組
"""
import pandas as pd
import numpy as np


class FundamentalAnalysis:
    """月營收 / PER / PBR / 財報分析"""

    def analyze(
        self,
        revenue_df: pd.DataFrame,
        per_df: pd.DataFrame,
        financial_df: pd.DataFrame = None,
    ) -> dict:
        """
        完整基本面分析
        revenue_df: 月營收
        per_df: PER/PBR
        financial_df: 綜合損益表
        """
        result = {}
        result["revenue"] = self._analyze_revenue(revenue_df)
        result["valuation"] = self._analyze_valuation(per_df)
        result["financial"] = self._analyze_financial(financial_df)
        result["signals"] = self._generate_signals(result)
        result["score"] = self._calc_score(result)
        return result

    # ─── 月營收分析 ─────────────────────────────────────────────

    def _analyze_revenue(self, df: pd.DataFrame) -> dict:
        if df is None or len(df) == 0:
            return {"error": "無營收資料"}

        df = df.copy().sort_values("date")
        last = df.iloc[-1]

        revenue = int(last.get("revenue", 0))
        revenue_date = str(last["date"].date()) if hasattr(last["date"], "date") else str(last["date"])

        # YoY
        yoy = last.get("revenue_year_over_year", None)
        if yoy is not None:
            yoy = round(float(yoy), 2)

        # MoM
        mom = last.get("revenue_month_over_month", None)
        if mom is not None:
            mom = round(float(mom), 2)

        # 累計營收
        cum_revenue = last.get("revenue_cumulative", None)
        if cum_revenue is not None:
            cum_revenue = int(cum_revenue)

        # 營收趨勢 (近6個月)
        if len(df) >= 6:
            recent_6 = df.tail(6)
            rev_values = recent_6["revenue"].values
            trend = "上升" if rev_values[-1] > rev_values[0] else "下降"
        else:
            trend = "資料不足"

        return {
            "date": revenue_date,
            "revenue": revenue,
            "revenue_str": f"{revenue / 1e8:.1f} 億" if revenue > 1e8 else f"{revenue / 1e4:.0f} 萬",
            "yoy": yoy,
            "mom": mom,
            "cumulative": cum_revenue,
            "trend": trend,
        }

    # ─── 估值分析 ───────────────────────────────────────────────

    def _analyze_valuation(self, df: pd.DataFrame) -> dict:
        if df is None or len(df) == 0:
            return {"error": "無估值資料"}

        df = df.copy().sort_values("date")
        last = df.iloc[-1]

        per = last.get("PER", None)
        pbr = last.get("PBR", None)
        div_yield = last.get("dividend_yield", None)

        if per is not None:
            per = round(float(per), 2)
        if pbr is not None:
            pbr = round(float(pbr), 2)
        if div_yield is not None:
            div_yield = round(float(div_yield), 2)

        # PER 歷史分位
        per_percentile = None
        if per is not None and len(df) >= 20:
            per_values = df["PER"].dropna().astype(float)
            if len(per_values) > 0:
                per_percentile = round(
                    (per_values < per).sum() / len(per_values) * 100, 1
                )

        # 估值狀態
        if per is not None:
            if per < 0:
                val_status = "虧損"
            elif per < 10:
                val_status = "便宜"
            elif per < 20:
                val_status = "合理"
            elif per < 30:
                val_status = "偏貴"
            else:
                val_status = "昂貴"
        else:
            val_status = "無資料"

        return {
            "PER": per,
            "PBR": pbr,
            "dividend_yield": div_yield,
            "per_percentile": per_percentile,
            "status": val_status,
        }

    # ─── 財報分析 ───────────────────────────────────────────────

    def _analyze_financial(self, df: pd.DataFrame) -> dict:
        if df is None or len(df) == 0:
            return {"error": "無財報資料"}

        df = df.copy().sort_values("date")

        # 取最近一季
        latest_date = df["date"].max()
        latest = df[df["date"] == latest_date]

        metrics = {}
        for _, row in latest.iterrows():
            metric_type = row.get("type", "")
            value = row.get("value", 0)
            metrics[metric_type] = float(value) if value else 0

        # 提取關鍵指標
        gross_margin = metrics.get("GrossProfit", None)
        operating_income = metrics.get("OperatingIncome", None)
        net_income = metrics.get("NetIncome", None)
        revenue = metrics.get("Revenue", None)
        eps = metrics.get("EPS", None)

        # 計算比率
        gross_margin_pct = None
        operating_margin_pct = None
        if revenue and revenue > 0:
            if gross_margin is not None:
                gross_margin_pct = round(gross_margin / revenue * 100, 2)
            if operating_income is not None:
                operating_margin_pct = round(operating_income / revenue * 100, 2)

        return {
            "date": str(latest_date.date()) if hasattr(latest_date, "date") else str(latest_date),
            "eps": round(eps, 2) if eps else None,
            "gross_margin_pct": gross_margin_pct,
            "operating_margin_pct": operating_margin_pct,
        }

    # ─── 訊號產生 ───────────────────────────────────────────────

    def _generate_signals(self, result: dict) -> list:
        signals = []
        rev = result.get("revenue", {})
        val = result.get("valuation", {})

        yoy = rev.get("yoy")
        if yoy is not None:
            if yoy > 30:
                signals.append(("✅", f"營收年增率 +{yoy}% 大幅成長"))
            elif yoy > 10:
                signals.append(("✅", f"營收年增率 +{yoy}% 穩健成長"))
            elif yoy < -10:
                signals.append(("⚠️", f"營收年增率 {yoy}% 衰退"))

        mom = rev.get("mom")
        if mom is not None and mom > 20:
            signals.append(("✅", f"營收月增率 +{mom}% 月增顯著"))

        per = val.get("PER")
        if per is not None:
            if 0 < per < 10:
                signals.append(("✅", f"本益比 {per} 偏低"))
            elif per > 30:
                signals.append(("⚠️", f"本益比 {per} 偏高"))

        div_yield = val.get("dividend_yield")
        if div_yield is not None and div_yield > 5:
            signals.append(("✅", f"殖利率 {div_yield}% 高殖利率"))

        return signals

    # ─── 基本面評分 (1-10) ──────────────────────────────────────

    def _calc_score(self, result: dict) -> int:
        score = 5
        rev = result.get("revenue", {})
        val = result.get("valuation", {})

        # 營收成長
        yoy = rev.get("yoy")
        if yoy is not None:
            if yoy > 30:
                score += 2
            elif yoy > 10:
                score += 1
            elif yoy < -10:
                score -= 1
            elif yoy < -30:
                score -= 2

        # 估值
        per = val.get("PER")
        if per is not None:
            if 0 < per < 12:
                score += 1
            elif per > 30:
                score -= 1

        # 殖利率
        div_yield = val.get("dividend_yield")
        if div_yield is not None:
            if div_yield > 5:
                score += 1
            elif div_yield > 3:
                score += 0.5

        return max(1, min(10, round(score)))
