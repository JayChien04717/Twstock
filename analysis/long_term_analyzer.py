"""
AI 台股分析師 — 長期價值分析器 (Long-term Fundamental Analyzer)
專注於 1 年以上的存股與價值投資，依賴財報、估值模型 (PE, PEG) 與殖利率。

買賣價位方法論 (價值投資):
  - 買點: 便宜區間 (歷史 PE 低位) / 高殖利率 (>5%) 之安全邊際
  - 賣點: 昂貴區間 (歷史 PE 高位) / 基本面轉差 (YoY < -10%)
  - 方法: 本益比估值法 (PE Valuation) / 股息殖利率評價法
"""

class LongTermAnalyzer:
    def analyze(self, fund: dict, tech: dict) -> dict:
        action = "觀望"
        reason_parts = []
        score = 0
        
        val = fund.get("valuation", {})
        rev = fund.get("revenue", {})
        latest = tech.get("latest", {})
        financial = fund.get("financial", {})
        
        current_price = latest.get("close")
        
        if fund.get("score", 0) == 0 and not val and not rev:
            return {
                "timeframe": "長期存股 (1年以上)",
                "action": "無資料",
                "reason": "缺乏歷史財務或營收數據，無法評估長期投資價值。",
                "buy_range": "N/A",
                "sell_range": "N/A",
                "price_basis": "無數據支持"
            }

        # 1. PE 估值 (本益比)
        per = val.get("PER", None)
        per_status = val.get("status", "")
        per_pct = val.get("per_percentile", 50)
        
        if "便宜" in per_status or (per_pct is not None and per_pct < 20):
            score += 3
            reason_parts.append(f"歷史本益比區間顯示目前為『低估』水位 (PE: {per}, 分位: {per_pct}%)")
        elif "昂貴" in per_status or (per_pct is not None and per_pct > 80):
            score -= 3
            reason_parts.append(f"歷史本益比區間顯示目前已嚴重『高估』 (PE: {per}, 分位: {per_pct}%)")
        elif "合理" in per_status:
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
            
        reason = "；".join(reason_parts) if reason_parts else "基本面表現平庸，目前估值合理但缺乏亮點，建議以長線資金觀察其盈餘表現。"
        
        # ── 買賣價位計算 (方法論: PE 估值與殖利率) ──
        buy_range, sell_range, price_basis = _calc_long_price(
            current_price, per, per_status, yield_pct, yoy, action
        )

        return {
            "timeframe": "長期存股 (1年以上)",
            "score": score,
            "action": action,
            "reason": reason,
            "buy_range": buy_range,
            "sell_range": sell_range,
            "price_basis": price_basis
        }

def _calc_long_price(price, per, status, yield_pct, yoy, action):
    """
    長期買賣價位根據本益比與殖利率計算。
    方法論:
      ① PE 估值法: 以歷史平均或合理 PE (12-15x) 作為參考
      ② 殖利率評價: 以 5% 作為安全邊際支撐
    """
    basis_parts = []
    
    if not price:
        return "N/A", "N/A", "缺乏現價資訊"

    # 1. 決定買點
    if "便宜" in status or (yield_pct and yield_pct > 5):
        buy_range = f"目前價位 {price} 具備高度安全邊際，可積極佈局"
        basis_parts.append(f"💎 方法: 價值投資模型 (PE {per} 偏低 / 殖利率 {yield_pct}% 護盤)")
    elif "合理" in status:
        buy_low = round(price * 0.9, 2)
        buy_high = round(price * 0.95, 2)
        buy_range = f"{buy_low} ~ {buy_high} (待回測分批進場)"
        basis_parts.append(f"💎 方法: 合理估值打 9 折買進策略 (PE {per} 合理)")
    elif "昂貴" in status:
        buy_range = "不建議進場，待估值修正"
        basis_parts.append(f"⚠️ 方法: 估值過高 (PE {per})，需等待市場冷卻")
    else:
        buy_range = f"回測年線或價格低於 {round(price * 0.85, 2)} 再考慮"
        basis_parts.append("📊 方法: 等待基本面追平股價或大規模修正")

    # 2. 決定目標賣點 (長期持有的情況)
    if per and per > 0:
        # 以 PE 25 作為初步獲利了結點
        target_pe = 22 if per < 15 else per * 1.3
        target_price = round(price * (target_pe / per), 2)
        sell_range = f"長期目標: {target_price} (PE 達 {round(target_pe, 1)}x)"
        basis_parts.append(f"🎯 目標價: 預期本益比擴張至 {round(target_pe, 1)}x")
    else:
        sell_range = "長期持有直至 YoY 連續衰退"
        basis_parts.append("🎯 目標: 基本面反轉前持續抱牢 (YoY 觀測)")

    # 3. 停損說明
    if yoy and yoy < -20:
        basis_parts.append("🛑 警示: 營收連月大幅衰退為長線停利/停損訊號")
    else:
        basis_parts.append("🛑 策略: 長期投資若基本面未轉惡，不建議頻繁停損")

    return buy_range, sell_range, "；".join(basis_parts)
