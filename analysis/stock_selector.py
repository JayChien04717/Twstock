"""
AI 台股分析師 — 選股引擎
"""
import pandas as pd
from config import SCORE_WEIGHTS


class StockSelector:
    """多面向加權評分選股引擎"""

    def __init__(self, weights: dict = None):
        self.weights = weights or SCORE_WEIGHTS

    def rank(self, analysis_results: dict) -> list:
        """
        對所有已分析的股票進行評分排名
        analysis_results: {stock_id: {technical: {...}, chip: {...}, fundamental: {...}}}
        returns: 排序後的股票列表
        """
        ranked = []

        for stock_id, analysis in analysis_results.items():
            tech_score = analysis.get("technical", {}).get("score", 5)
            chip_score = analysis.get("chip", {}).get("score", 5)
            fund_score = analysis.get("fundamental", {}).get("score", 5)

            # 加權總分
            total = (
                tech_score * self.weights["technical"]
                + chip_score * self.weights["chip"]
                + fund_score * self.weights["fundamental"]
            )

            # 收集所有訊號
            signals = []
            for key in ["technical", "chip", "fundamental"]:
                sigs = analysis.get(key, {}).get("signals", [])
                signals.extend(sigs)

            # 星星評等
            stars = self._to_stars(total)

            ranked.append({
                "stock_id": stock_id,
                "name": analysis.get("name", stock_id),
                "tech_score": tech_score,
                "chip_score": chip_score,
                "fund_score": fund_score,
                "total_score": round(total, 2),
                "stars": stars,
                "signals": signals,
                "latest": analysis.get("technical", {}).get("latest", {}),
            })

        # 按總分排序
        ranked.sort(key=lambda x: x["total_score"], reverse=True)
        return ranked

    def top_picks(self, ranked: list, n: int = 10) -> list:
        """取得推薦前 N 名"""
        return ranked[:n]

    def risk_alerts(self, ranked: list) -> list:
        """找出有風險警示的股票"""
        alerts = []
        for stock in ranked:
            warnings = [s for s in stock["signals"] if s[0] == "⚠️"]
            if len(warnings) >= 2:
                alerts.append({
                    "stock_id": stock["stock_id"],
                    "name": stock["name"],
                    "warnings": warnings,
                    "total_score": stock["total_score"],
                })
        return alerts

    def _to_stars(self, score: float) -> str:
        """評分轉星星"""
        if score >= 8:
            return "★★★★★"
        elif score >= 6.5:
            return "★★★★☆"
        elif score >= 5:
            return "★★★☆☆"
        elif score >= 3.5:
            return "★★☆☆☆"
        else:
            return "★☆☆☆☆"
