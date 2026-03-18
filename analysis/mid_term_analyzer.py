"""
AI 台股分析師 — 中長波段分析器 (Mid-term Swing Analyzer)
專注於 2-4 週的波段操作，主要看趨勢 (MACD, 布林通道, 均線排列) 與相型理論 (Darvas Box)。

買賣價位方法論 (Darvas Box + 均線):
  - 買點: Darvas Box 箱底 +1% (突破確認)  /  MACD 黃金交叉後 MA20 支撐
  - 賣點: Darvas Box 箱頂 -1% (獲利了結)  /  均線死叉後目標
  - 停損: 跌破箱底 / 跌破 MA20 月線
"""


class MidTermAnalyzer:
    def analyze(self, tech: dict, chip: dict) -> dict:
        action = "觀望"
        reason_parts = []
        score = 0

        ma = tech.get("ma", {})
        macd = tech.get("macd", {})
        darvas = tech.get("darvas_box", {})
        latest = tech.get("latest", {})
        boll = tech.get("bollinger", {})

        current_price = latest.get("close")
        ma20 = ma.get("MA20")
        ma60 = ma.get("MA60")

        # ── 1. 均線趨勢 (MA20 月線 與 MA60 季線) ─────────────────
        arrangement = ma.get("arrangement", "")
        if "多頭" in arrangement:
            score += 2
            reason_parts.append(f"均線呈多頭排列 (MA20={ma20}, MA60={ma60})，長多保護短波段")
        elif "空頭" in arrangement:
            score -= 2
            reason_parts.append(f"均線空頭排列 (MA20={ma20}, MA60={ma60})，趨勢向下難有波段行情")

        # ── 2. MACD 波段趨勢轉折 ──────────────────────────────────
        macd_cross = macd.get("cross", "無")
        if macd.get("trend") == "偏多":
            score += 1
            reason_parts.append(f"MACD 零軸以上偏多格局 (DIF={macd.get('DIF')}, MACD={macd.get('MACD')})")

        if macd_cross == "黃金交叉":
            score += 1
            reason_parts.append("MACD 柱狀體剛翻正，有波段發動可能")
        elif macd_cross == "死亡交叉":
            score -= 1
            reason_parts.append("MACD 波段高檔死叉，需留意出場點")

        # ── 3. 相型理論 (Darvas Box) ───────────────────────────────
        darvas_trend = darvas.get("trend", "")
        current_top    = darvas.get("current_top")
        current_bottom = darvas.get("current_bottom")

        if "強勢突破" in darvas_trend:
            score += 3
            reason_parts.append(
                f"強勢突破前波 Darvas 箱頂 ({current_top})，相型論定義波段目標上移"
            )
        elif "弱勢跌破" in darvas_trend:
            score -= 3
            reason_parts.append(
                f"跌穿 Darvas 波段防守點 ({current_bottom})，趨勢已破壞"
            )
        elif "箱型整理" in darvas_trend:
            reason_parts.append(
                f"Darvas 箱型區間: {current_bottom} ~ {current_top}，等待方向突破"
            )

        # ── 4. 布林通道輔助 ───────────────────────────────────────
        boll_pos = boll.get("position", "")
        if boll_pos == "中軌上方":
            score += 1
            reason_parts.append(f"股價在布林中軌 ({boll.get('mid')}) 上方，短期趨勢偏多")
        elif boll_pos == "中軌下方":
            score -= 1
            reason_parts.append(f"股價在布林中軌 ({boll.get('mid')}) 下方，短期趨勢偏空")

        # ── 5. 籌碼穩定度 (外資或投信連續買超) ───────────────────
        inst = chip.get("institutional", {})
        trend_chip = inst.get("trend", "")
        if "同步買超" in trend_chip or "認錯回補" in trend_chip:
            score += 2
            reason_parts.append("法人波段積極籌碼進駐，強化上漲動能")
        elif "同步賣超" in trend_chip:
            score -= 2
            reason_parts.append("法人波段籌碼正快速流失，壓抑波段空間")

        # ── 綜合判定 Action ──────────────────────────────────────
        if score >= 5:
            action = "強烈買進 (波段突破)"
        elif score >= 2:
            action = "逢低佈局"
        elif score <= -3:
            action = "強烈賣出 (停損/停利)"
        elif score <= -1:
            action = "減碼觀望"

        reason = "；".join(reason_parts) if reason_parts else "目前處於盤整模糊期，波段趨勢不明顯，建議觀望。"

        # ── 買賣價位計算 (方法論: Darvas Box 相型 + 均線) ─────────
        buy_range, sell_range, price_basis = _calc_mid_price(
            darvas, current_price, ma20, ma60, boll, macd_cross, action
        )

        return {
            "timeframe": "中長波段 (2-4週)",
            "score": score,
            "action": action,
            "reason": reason,
            "buy_range": buy_range,
            "sell_range": sell_range,
            "price_basis": price_basis,
        }


# ─── 中線價位輔助函數 ────────────────────────────────────────────────

def _calc_mid_price(darvas, price, ma20, ma60, boll, macd_cross, action):
    """
    中線買賣價位: 優先採用 Darvas Box 箱型理論，輔以均線與 MACD 交叉。
    方法論:
      ① Darvas Box — 箱底 +1% 買進，箱頂 -1% 賣出，箱底 -1% 停損
      ② 突破格局  — 現價追, 以前箱頂為停損
      ③ 弱勢格局  — 不建議買, 反彈至箱底減碼
      ④ 缺乏Box   — 改用 MA20±2% 作為波段基準
    """
    basis_parts = []
    trend = darvas.get("trend", "")
    box_top    = darvas.get("current_top")
    box_bottom = darvas.get("current_bottom")
    darvas_buy  = darvas.get("buy_price")
    darvas_sell = darvas.get("sell_price")
    darvas_reason = darvas.get("reason", "")

    if action in ["強烈賣出 (停損/停利)", "減碼觀望"]:
        buy_range = "不建議進場"
        if box_bottom and price:
            sell_range = f"反彈至 {box_bottom} ~ {round(box_bottom*1.02,2)} 附近減碼"
            basis_parts.append(f"📉 Darvas Box 趨勢轉空，前箱底 {box_bottom} 轉為反彈壓力")
        elif ma20 and price:
            sell_range = f"反彈至 MA20 ({ma20}) 附近減碼"
            basis_parts.append(f"📉 均線空頭排列，MA20 ({ma20}) 為反彈首要壓力")
        else:
            sell_range = "反彈現價附近減碼"
            basis_parts.append("📉 趨勢偏弱，建議逢彈減碼")
        return buy_range, sell_range, "；".join(basis_parts)

    # 有成型的 Darvas Box
    if "箱型整理" in trend and box_top and box_bottom:
        buy_low  = round(box_bottom * 1.005, 2)
        buy_high = round(box_bottom * 1.015, 2)
        buy_range = f"{buy_low} ~ {buy_high}"

        sell_low  = round(box_top * 0.97, 2)
        sell_high = round(box_top * 0.99, 2)
        sell_range = f"目標: {sell_low} ~ {sell_high} (箱頂 {box_top} 附近出場)"

        stop_loss = round(box_bottom * 0.99, 2)
        basis_parts.append(f"📦 方法: Darvas Box 相型理論")
        basis_parts.append(f"   箱型區間: {box_bottom} ~ {box_top}")
        basis_parts.append(f"   買點: 接近箱底 {box_bottom} +0.5~1.5% 確認支撐")
        basis_parts.append(f"   目標: 箱頂 {box_top} 附近 (-1~3%) 分批賣出")
        basis_parts.append(f"🛑 停損: 跌破箱底 {box_bottom} → 停損位 {stop_loss}")
        if darvas_reason:
            basis_parts.append(f"📝 {darvas_reason}")

    elif "強勢突破" in trend:
        buy_range = darvas_buy or (f"現價 {price} 附近" if price else "現價附近追進")
        sell_range = darvas_sell or (f"{box_top} (前箱頂停損)" if box_top else "觀察前高")

        basis_parts.append(f"🚀 方法: Darvas Box 突破追強策略")
        if box_top:
            basis_parts.append(f"   股價已突破舊箱頂 {box_top}，新箱子建構中")
            basis_parts.append(f"🛑 停損: 跌回舊箱頂 {box_top} 以下")
        basis_parts.append(f"   MACD {'黃金交叉，動能確認突破有效' if macd_cross=='黃金交叉' else '尚未交叉，注意假突破風險'}")

    elif "弱勢跌破" in trend:
        buy_range = "暫不建議買進，等新Darvas Box成型"
        sell_range = darvas_sell or (f"反彈至前箱底 {box_bottom} 附近出場" if box_bottom else "觀察反彈壓力")
        basis_parts.append(f"⬇️ 方法: Darvas Box 跌破後的守勢策略")
        if box_bottom:
            basis_parts.append(f"   已跌破舊箱底 {box_bottom}，趨勢轉弱，等待新底部確立")
        basis_parts.append("   建議空手等待新Darvas Box完整成型後再行動")

    else:
        # 無 Darvas Box → 改用 MA20 波段基準
        if ma20 and price:
            buy_low  = round(ma20 * 0.99, 2)
            buy_high = round(ma20 * 1.01, 2)
            buy_range = f"{buy_low} ~ {buy_high}"

            if boll and boll.get("upper"):
                target = round(boll["upper"] * 0.98, 2)
                sell_range = f"目標: {target} (布林上軌 {boll['upper']} 附近)"
                basis_parts.append(f"📊 方法: 均線波段策略 (Darvas Box 未成型)")
                basis_parts.append(f"   買點: MA20 ({ma20}) 支撐±1%")
                basis_parts.append(f"   目標: 布林上軌 {boll['upper']} 附近")
            else:
                target = round(ma20 * 1.08, 2)
                sell_range = f"目標: {target} (MA20 +8% 波段目標)"
                basis_parts.append(f"📊 方法: MA20 均線波段策略")
                basis_parts.append(f"   買點: MA20 ({ma20}) ±1% 支撐帶")
            basis_parts.append(f"🛑 停損: 跌破 MA20 ({ma20}) 出場")
        else:
            buy_range  = "箱型尚未成型，等待訊號"
            sell_range = "等待明確支撐/壓力確立"
            basis_parts.append("📊 Darvas Box 尚未成型，建議等待均線+箱型雙確認")

    return buy_range, sell_range, "；".join(basis_parts)
