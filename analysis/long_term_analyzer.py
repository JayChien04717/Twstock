"""
AI 台股分析師 — 長期價值分析器 (Long-term Fundamental Analyzer)
專注於 1 年以上的存股與價值投資，依賴財報、估值模型 (PE, PEG) 與殖利率。
"""

class LongTermAnalyzer:
    def analyze(self, fund: dict, tech: dict) -> dict:
        action = "觀望"
        reason_parts = []
        score = 0
        
        val = fund.get("valuation", {})
        rev = fund.get("revenue", {})
        latest = tech.get("latest", {})
        
        if fund.get("score", 0) == 0 and not val and not rev:
            return {
                "timeframe": "長期存股 (1年以上)",
                "action": "無資料",
                "reason": "缺乏歷史財務或營收數據，無法評估長期投資價值。",
                "buy_range": "N/A",
                "sell_range": "N/A"
            }

        # 1. PE 估值 (本益比)
        per = val.get("PER", None)
        status = val.get("status", "")
        if "低估" in status:
            score += 3
            reason_parts.append(f"歷史本益比區間顯示目前為『低估』水位 (PE: {per})")
        elif "高估" in status:
            score -= 3
            reason_parts.append(f"歷史本益比區間顯示目前已嚴重『高估』 (PE: {per})")
        elif "合理" in status:
            score += 1
            reason_parts.append(f"PE 處於合理水準 ({per})")
            
        # 2. 營收成長動能 (YoY)
        yoy = rev.get("yoy", None)
        if yoy is not None:
            if yoy > 20:
                score += 2
                reason_parts.append(f"單月營收爆發成長 (YoY +{yoy}%)，長期業績動能強勁")
            elif yoy > 5:
                score += 1
                reason_parts.append(f"營收維持穩健成長 (YoY +{yoy}%)")
            elif yoy < -10:
                score -= 2
                reason_parts.append(f"營收嚴重衰退 (YoY {yoy}%)，需留意基本面是否轉惡")

        # 3. 殖利率 (安全邊際)
        yield_pct = val.get("dividend_yield", None)
        if yield_pct is not None:
            if yield_pct > 5:
                score += 2
                reason_parts.append(f"高殖利率保護傘 ({yield_pct}%)，適合長線存股等待價值發酵")
            elif yield_pct < 2 and per and per > 25:
                score -= 1
                reason_parts.append(f"低殖利率 ({yield_pct}%) 且高本益比，長線投資缺乏安全邊際保護")

        # 綜合判定 Action
        if score >= 5:
            action = "強烈買進 (價值浮現)"
        elif score >= 2:
            action = "分批建倉"
        elif score <= -3:
            action = "長期賣出 (基本面轉弱)"
        elif score <= -1:
            action = "減碼換股"
            
        reason = "；".join(reason_parts) if reason_parts else "基本面表現平庸，目前估值合理但缺乏亮點，建議以長線資金觀察器盈餘表現。"
        
        current_price = latest.get("close", None)
        buy_range = f"設定定期定額或逢大盤修正回測年線 (MA240) 建倉"
        sell_range = f"若 YoY 連續三個月轉負，或跌破起漲點則出場"
        
        if "低估" in status and current_price:
             buy_range = f"目前價位 ({current_price}) 已進入長線價值甜美區，可大膽買進"

        return {
            "timeframe": "長期存股 (1年以上)",
            "score": score,
            "action": action,
            "reason": reason,
            "buy_range": buy_range,
            "sell_range": sell_range
        }
