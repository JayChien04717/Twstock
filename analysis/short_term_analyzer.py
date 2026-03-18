"""
AI 台股分析師 — 短線分析器 (Short-term Analyzer)
專注於 1-5 天的短週期操作，主要看技術指標 (KD, RSI, 動能, 爆量) 與短期籌碼。
"""

class ShortTermAnalyzer:
    def analyze(self, tech: dict, chip: dict) -> dict:
        action = "觀望"
        reason_parts = []
        score = 0
        
        # 1. 動能指標 (ROC)
        momentum = tech.get("momentum", {})
        if momentum.get("status") == "強勢動能":
            score += 2
            reason_parts.append("短線動能強勁")
        elif momentum.get("status") == "弱勢動能":
            score -= 2
            reason_parts.append("短線動能偏弱")
            
        # 2. KD 與 RSI (超買/超賣反轉)
        kd = tech.get("kd", {})
        rsi = tech.get("rsi", {})
        
        if kd.get("cross") == "黃金交叉":
            score += 2
            reason_parts.append("KD 剛形成黃金交叉")
        elif kd.get("cross") == "死亡交叉":
            score -= 2
            reason_parts.append("KD 形成死亡交叉，短線有拉回風險")
            
        if rsi.get("status") == "超賣" or rsi.get("RSI6", 50) < 30:
            score += 1
            reason_parts.append(f"RSI 超賣 ({rsi.get('RSI6', 0)})，乖離過大有反彈契機")
        elif rsi.get("status") == "超買" or rsi.get("RSI6", 50) > 75:
            score -= 2
            reason_parts.append(f"RSI 進入超買區 ({rsi.get('RSI6', 0)})，短線追高風險大")

        # 3. 爆量檢查
        latest = tech.get("latest", {})
        if latest.get("vol_status") == "爆量" and latest.get("change_pct", 0) > 0:
            score += 1
            reason_parts.append("今日帶量上攻")
        elif latest.get("vol_status") == "爆量" and latest.get("change_pct", 0) < 0:
            score -= 2
            reason_parts.append("高檔爆量收黑，短線需警戒")
            
        # 4. 短期外資與投信
        inst = chip.get("institutional", {})
        investors = inst.get("investors", {})
        foreign = investors.get("外資", {})
        sitc = investors.get("投信", {})
        
        if foreign.get("net", 0) > 0 and sitc.get("net", 0) > 0:
            score += 2
            reason_parts.append("土洋法人短線同步買超認錯")
        elif foreign.get("net", 0) < 0 and foreign.get("consecutive_days", 0) >= 3:
            score -= 1
            reason_parts.append("外資連續賣超，形成短線反壓")

        # 綜合判定 Action
        if score >= 4:
            action = "強烈買進"
        elif score >= 2:
            action = "偏多操作"
        elif score <= -3:
            action = "強烈賣出 (或放空)"
        elif score <= -1:
            action = "短線減碼"
            
        reason = "；".join(reason_parts) if reason_parts else "短線無明顯技術破口或爆發訊號，建議觀望。"
        
        # 短線通常看 5 日線 (MA5) 取代支撐/壓力
        ma = tech.get("ma", {})
        ma5 = ma.get("MA5", None)
        ma10 = ma.get("MA10", None)
        current_price = latest.get("close", None)
        
        buy_range = f"{ma5} ~ {current_price}" if ma5 and current_price and current_price > ma5 else "暫不建議"
        sell_range = f"跌破 {ma5} 停損" if ma5 else "未定"
        
        if action in ["強烈賣出 (或放空)", "短線減碼"]:
            buy_range = "不建議"
            sell_range = f"現價 ({current_price})"

        return {
            "timeframe": "短期 (1-5天)",
            "score": score,
            "action": action,
            "reason": reason,
            "buy_range": buy_range,
            "sell_range": sell_range
        }
