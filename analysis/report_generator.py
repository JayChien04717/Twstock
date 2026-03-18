"""
AI 台股分析師 — 報告產生器
"""
from datetime import datetime


class ReportGenerator:
    """產出每日分析報告 (文字版 + HTML 版)"""

    def generate_text_report(
        self,
        date: str,
        top_picks: list,
        sector_rotation: dict,
        risk_alerts: list = None,
    ) -> str:
        """產出文字格式每日報告"""
        lines = []
        lines.append("")
        lines.append(f"📊 每日台股 AI 分析報告 — {date}")
        lines.append("━" * 50)

        # ─── 選股推薦 ──────────────────────────────────────────
        lines.append("")
        lines.append("🎯 AI 選股推薦 Top 10")
        lines.append("─" * 40)
        for i, stock in enumerate(top_picks[:10], 1):
            latest = stock.get("latest", {})
            close = latest.get("close", "N/A")
            change_pct = latest.get("change_pct", 0)
            arrow = "↑" if change_pct > 0 else "↓" if change_pct < 0 else "→"
            lines.append(
                f"  {i:2d}. {stock['stock_id']} {stock['name']:<8s} "
                f"{stock['stars']}  "
                f"總分:{stock['total_score']:.1f}  "
                f"(技:{stock['tech_score']} 籌:{stock['chip_score']} 基:{stock['fund_score']})"
            )
            lines.append(
                f"      收盤:{close}  {arrow}{change_pct:+.2f}%"
            )
            # 重要訊號
            key_signals = stock.get("signals", [])[:3]
            if key_signals:
                sig_str = " | ".join([f"{s[0]} {s[1]}" for s in key_signals])
                lines.append(f"      {sig_str}")
            
            # 💡 建議價位與理由
            advice = stock.get("advice", {})
            for term, data in advice.items():
                if data.get("action") not in ["觀望", "無資料", "減碼觀望"]:
                    term_label = "短" if term == "short_term" else ("中" if term == "mid_term" else "長")
                    lines.append(f"      [{term_label}] 買:{data.get('buy_range')}  賣:{data.get('sell_range')}")
                    if data.get("price_basis"):
                        lines.append(f"          └─ {data.get('price_basis')}")
            lines.append("")

        # ─── 族群資金輪動 ──────────────────────────────────────
        lines.append("🔄 族群資金輪動")
        lines.append("─" * 40)

        summary = sector_rotation.get("summary", {})
        details = summary.get("details", [])
        for detail in details:
            lines.append(f"  【{detail['period']}】")
            lines.append(f"    💹 流入: {detail['inflow']}")
            lines.append(f"    💸 流出: {detail['outflow']}")

        rotation = summary.get("rotation", "")
        if rotation:
            lines.append(f"")
            lines.append(f"  🧭 趨勢: {rotation}")

        # ─── 各天數族群排行 ─────────────────────────────────────
        for key in ["1d", "3d", "5d"]:
            data = sector_rotation.get(key, {})
            if "error" in data:
                continue
            lines.append(f"")
            lines.append(f"  📊 {key.replace('d', '')} 日族群排行:")
            inflow = data.get("top_inflow", {})
            outflow = data.get("top_outflow", {})
            for sector, val in sorted(inflow.items(), key=lambda x: -x[1])[:5]:
                lines.append(f"    🟢 {sector}: +{val:>12,} 張")
            for sector, val in sorted(outflow.items(), key=lambda x: x[1])[:5]:
                lines.append(f"    🔴 {sector}: {val:>13,} 張")

        # ─── 風險警示 ──────────────────────────────────────────
        if risk_alerts:
            lines.append("")
            lines.append("⚠️ 風險警示")
            lines.append("─" * 40)
            for alert in risk_alerts[:5]:
                lines.append(f"  {alert['stock_id']} {alert['name']} (分數:{alert['total_score']:.1f})")
                for w in alert["warnings"]:
                    lines.append(f"    {w[0]} {w[1]}")

        lines.append("")
        lines.append("━" * 50)
        lines.append(f"⏰ 報告產出時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("📌 以上分析僅供參考，投資請自行評估風險")
        lines.append("")

        return "\n".join(lines)

    def generate_html_data(
        self,
        date: str,
        ranked_stocks: list,
        sector_rotation: dict,
        stock_analyses: dict,
    ) -> dict:
        """產出 HTML 前端需要的 JSON 資料"""
        # 限制只傳送前 50 名，避免全市場掃描時 JSON 過大導致前端崩潰
        top_n = 50
        trimmed_ranked = ranked_stocks[:top_n]
        trimmed_analyses = {
            s["stock_id"]: self._serialize_analysis(stock_analyses[s["stock_id"]])
            for s in trimmed_ranked
            if s["stock_id"] in stock_analyses
        }

        return {
            "date": date,
            "top_picks": ranked_stocks[:10],
            "all_stocks": trimmed_ranked,
            "sector_rotation": self._serialize_rotation(sector_rotation),
            "stock_analyses": trimmed_analyses,
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

    def _clean_nan(self, obj):
        """遞迴清理 dictionary，把 NaN, Infinity 換成 None，確保 JSON 格式正確"""
        import math
        if isinstance(obj, float):
            if math.isnan(obj) or math.isinf(obj):
                return None
            return obj
        elif isinstance(obj, dict):
            return {k: self._clean_nan(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._clean_nan(v) for v in obj]
        return obj

    def _serialize_rotation(self, rotation: dict) -> dict:
        """確保所有值可 JSON 序列化且無 NaN"""
        import json
        clean = self._clean_nan(rotation)
        return json.loads(json.dumps(clean, default=str))

    def _serialize_analysis(self, analysis: dict) -> dict:
        """確保分析結果可 JSON 序列化且無 NaN"""
        import json
        clean = self._clean_nan(analysis)
        return json.loads(json.dumps(clean, default=str))
