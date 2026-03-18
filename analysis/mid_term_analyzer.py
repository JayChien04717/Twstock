"""
AI 台股分析師 — 中長波段分析器 (Mid-term Swing Analyzer)
專注於 2-4 週的波段操作，主要看趨勢 (MACD, 布林通道, 均線排列) 與相型理論 (Darvas Box)。
"""

class MidTermAnalyzer:
    def analyze(self, tech: dict, chip: dict) -> dict:
        action = "觀望"
        reason_parts = []
        score = 0
        
        # 1. 均線趨勢 (MA20 月線 與 MA60 季線)
        ma = tech.get("ma", {})
        arrangement = ma.get("arrangement", "")
        if "多頭" in arrangement:
            score += 2
            reason_parts.append("均線呈多頭排列，長多保護短波段")
        elif "空頭" in arrangement:
            score -= 2
            reason_parts.append("均線空頭排列，趨勢向下難有波段行情")
            
        # 2. MACD (波段趨勢轉折)
        macd = tech.get("macd", {})
        if macd.get("trend") == "偏多":
            score += 1
            reason_parts.append("MACD 零軸以上偏多格局")
            
        if macd.get("cross") == "黃金交叉":
            score += 1
            reason_parts.append("MACD 柱狀體剛翻正，有波段發動可能")
        elif macd.get("cross") == "死亡交叉":
            score -= 1
            reason_parts.append("MACD 波段高檔死叉，需留意出場點")

        # 3. 相型理論 (Darvas Box)
        darvas = tech.get("darvas_box", {})
        trend = darvas.get("trend", "")
        current_top = darvas.get("current_top", None)
        current_bottom = darvas.get("current_bottom", None)
        
        if "強勢突破" in trend:
            score += 3
            reason_parts.append(f"強勢突破前波箱型頂部 ({current_top})，波段目標價上移")
        elif "弱勢跌破" in trend:
            score -= 3
            reason_parts.append(f"跌穿波段防守點 ({current_bottom})，趨勢已破壞")
        elif "箱型整理" in trend:
            reason_parts.append(f"箱型震盪區間: {current_bottom} ~ {current_top}")

        # 4. 籌碼穩定度 (外資或投信連續買超)
        inst = chip.get("institutional", {})
        trend_chip = inst.get("trend", "")
        if "同步買超" in trend_chip or "認錯回補" in trend_chip:
            score += 2
            reason_parts.append("法人波段積極籌碼進駐")
        elif "同步賣超" in trend_chip:
            score -= 2
            reason_parts.append("法人波段籌碼正快速流失")

        # 綜合判定 Action
        if score >= 5:
            action = "強烈買進 (波段突破)"
        elif score >= 2:
            action = "逢低佈局"
        elif score <= -3:
            action = "強烈賣出 (停損/停利)"
        elif score <= -1:
            action = "減碼觀望"
            
        reason = "；".join(reason_parts) if reason_parts else "目前處於盤整模糊期，波段趨勢不明顯，建議觀望。"
        
        # 買賣區間直接借用 Darvas Box 的建議
        buy_range = darvas.get("buy_price", "視法人買超成本而定")
        sell_range = darvas.get("sell_price", "跌破前波起漲點停損")

        return {
            "timeframe": "中長波段 (2-4週)",
            "score": score,
            "action": action,
            "reason": reason,
            "buy_range": buy_range,
            "sell_range": sell_range
        }
