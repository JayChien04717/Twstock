"""
AI 台股分析師 — 短線分析器 (Short-term Analyzer)
專注於 1-5 天的短週期操作，主要看技術指標 (KD, RSI, 動能, 爆量) 與短期籌碼。

買賣價位方法論 (K線 + 技術指標):
  - 買點: MA5 / 布林下軌 / 前日低點支撐
  - 賣點 / 停損: MA5 跌破停損 / 布林上軌獲利了結
"""


class ShortTermAnalyzer:
    def analyze(self, tech: dict, chip: dict) -> dict:
        action = "觀望"
        reason_parts = []
        score = 0

        # 取出常用數值
        latest = tech.get("latest", {})
        ma = tech.get("ma", {})
        boll = tech.get("bollinger", {})
        kd = tech.get("kd", {})
        rsi = tech.get("rsi", {})
        momentum = tech.get("momentum", {})

        current_price = latest.get("close")
        ma5  = ma.get("MA5")
        ma10 = ma.get("MA10")
        ma20 = ma.get("MA20")
        boll_upper = boll.get("upper")
        boll_mid   = boll.get("mid")
        boll_lower = boll.get("lower")

        # ── 1. 動能指標 (ROC) ─────────────────────────────────────
        if momentum.get("status") == "強勢動能":
            score += 2
            reason_parts.append("短線動能強勁 (ROC10/20 雙正)")
        elif momentum.get("status") == "弱勢動能":
            score -= 2
            reason_parts.append("短線動能偏弱 (ROC10/20 雙負)")

        # ── 2. KD 交叉 ───────────────────────────────────────────
        if kd.get("cross") == "黃金交叉":
            score += 2
            reason_parts.append(f"KD 黃金交叉 (K={kd.get('K', '-')}, D={kd.get('D', '-')})，短線翻多")
        elif kd.get("cross") == "死亡交叉":
            score -= 2
            reason_parts.append(f"KD 死亡交叉 (K={kd.get('K', '-')}, D={kd.get('D', '-')})，短線有拉回風險")

        # ── 3. RSI 超買超賣 ──────────────────────────────────────
        rsi6 = rsi.get("RSI6", 50)
        if rsi.get("status") == "超賣" or rsi6 < 30:
            score += 1
            reason_parts.append(f"RSI 超賣 ({rsi6})，技術面乖離過大，有短線反彈契機")
        elif rsi.get("status") == "超買" or rsi6 > 75:
            score -= 2
            reason_parts.append(f"RSI 超買 ({rsi6})，短線追高風險大")

        # ── 4. 布林通道位置 ──────────────────────────────────────
        boll_pos = boll.get("position", "")
        if boll_pos == "跌破下軌" and current_price and boll_lower:
            score += 1
            reason_parts.append(f"股價跌破布林下軌 ({boll_lower})，均值回歸反彈敏感區")
        elif boll_pos == "突破上軌" and current_price and boll_upper:
            score -= 1
            reason_parts.append(f"股價突破布林上軌 ({boll_upper})，短線擴張風險注意")

        # ── 5. 爆量訊號 ──────────────────────────────────────────
        if latest.get("vol_status") == "爆量" and latest.get("change_pct", 0) > 0:
            score += 1
            reason_parts.append(f"今日帶量上攻 (量能 {latest.get('vol_ratio', '-')}x)，短線買盤積極")
        elif latest.get("vol_status") == "爆量" and latest.get("change_pct", 0) < 0:
            score -= 2
            reason_parts.append(f"高檔爆量收黑 (量能 {latest.get('vol_ratio', '-')}x)，短線需警戒")

        # ── 6. 短期法人籌碼 ──────────────────────────────────────
        inst = chip.get("institutional", {})
        investors = inst.get("investors", {})
        foreign = investors.get("外資", {})
        sitc = investors.get("投信", {})

        if foreign.get("net", 0) > 0 and sitc.get("net", 0) > 0:
            score += 2
            reason_parts.append("土洋法人短線同步買超，籌碼面強力護盤")
        elif foreign.get("net", 0) < 0 and foreign.get("consecutive_days", 0) >= 3:
            score -= 1
            reason_parts.append("外資連續賣超，形成短線反壓")

        # ── 綜合判定 Action ──────────────────────────────────────
        if score >= 4:
            action = "強烈買進"
        elif score >= 2:
            action = "偏多操作"
        elif score <= -3:
            action = "強烈賣出 (或放空)"
        elif score <= -1:
            action = "短線減碼"

        reason = "；".join(reason_parts) if reason_parts else "短線無明顯技術破口或爆發訊號，建議觀望。"

        # ── 買賣價位計算 (方法論: K線均線 + 布林通道) ────────────
        buy_range, sell_range, price_basis = _calc_short_price(
            current_price, ma5, ma10, boll_lower, boll_upper, boll_mid, action, rsi6
        )

        return {
            "timeframe": "短期 (1-5天)",
            "score": score,
            "action": action,
            "reason": reason,
            "buy_range": buy_range,
            "sell_range": sell_range,
            "price_basis": price_basis,
        }


# ─── 短線價位輔助函數 ────────────────────────────────────────────────

def _calc_short_price(price, ma5, ma10, boll_lower, boll_upper, boll_mid, action, rsi6):
    """
    短線買賣價位根據 K 線技術指標計算，並說明理由。
    方法論優先順序：
      買點: ① RSI 超賣 → 布林下軌反彈  ② MA5 均線支撐  ③ 現價附近追強
      賣點: ① 布林上軌  ② RSI 超買  ③ MA5 跌破停損
    """
    basis_parts = []

    # ── 決定買點 ──────────────────────────────────────────────────
    if action in ["強烈賣出 (或放空)", "短線減碼"]:
        buy_range = "不建議進場"
        if price:
            sell_range = f"現價 {price} 附近減碼/停損"
        else:
            sell_range = "現價減碼/停損"
        basis_parts.append("📉 技術面偏弱，不建議短線買進")
        if ma5:
            basis_parts.append(f"跌破 MA5 ({ma5}) → 停損訊號")
        return buy_range, sell_range, "；".join(basis_parts)

    # 買進情境
    if rsi6 < 30 and boll_lower:
        # RSI 超賣 + 布林下軌: 反彈買點
        buy_low  = round(boll_lower * 0.99, 2)
        buy_high = round(boll_lower * 1.02, 2)
        buy_range = f"{buy_low} ~ {buy_high}"
        basis_parts.append(f"📊 方法: 布林下軌 ({boll_lower}) + RSI 超賣 ({rsi6})反彈區間")
    elif ma5 and price and price > ma5:
        # 多頭格局: MA5 拉回支撐買點
        buy_low  = round(ma5 * 0.99, 2)
        buy_high = round(ma5 * 1.01, 2)
        buy_range = f"{buy_low} ~ {buy_high}"
        basis_parts.append(f"📊 方法: MA5 ({ma5}) 均線支撐拉回買點 (±1%)")
    elif ma5 and price:
        buy_range = f"待確認突破 MA5 ({ma5}) 後追進"
        basis_parts.append(f"📊 方法: MA5 ({ma5}) 為短線多空分水嶺，需站上後確認")
    else:
        buy_range = f"現價 {price} 附近" if price else "參考現價"
        basis_parts.append("📊 方法: 均線資料不足，以現價為參考")

    # ── 決定賣點 ──────────────────────────────────────────────────
    if boll_upper:
        sell_upper = round(boll_upper * 0.99, 2)
        sell_range = f"目標: {sell_upper} (布林上軌 {boll_upper} 附近獲利了結)"
        basis_parts.append(f"🎯 目標價: 布林上軌 {boll_upper} (短線壓力)")
    elif ma10 and price and price < ma10:
        sell_range = f"壓力: {ma10} (MA10 壓力，反彈減碼)"
        basis_parts.append(f"🎯 目標價: MA10 ({ma10}) 反彈壓力位")
    elif ma5:
        sell_range = f"跌破 MA5 ({ma5}) 嚴格停損"
        basis_parts.append(f"🛑 停損: 跌破 MA5 ({ma5})")
    else:
        sell_range = "跌破買進成本 -3% 停損"
        basis_parts.append("🛑 停損: 買進成本 -3%")

    # ── 停損補充說明 ──────────────────────────────────────────────
    if ma5:
        basis_parts.append(f"🛑 停損線: MA5 ({ma5})，跌破出場")

    return buy_range, sell_range, "；".join(basis_parts)
