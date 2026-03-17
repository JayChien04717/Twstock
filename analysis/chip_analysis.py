"""
AI 台股分析師 — 籌碼面分析模組
"""
import pandas as pd
import numpy as np


class ChipAnalysis:
    """三大法人 / 融資融券 / 外資持股分析"""

    def analyze(self, institutional_df: pd.DataFrame, margin_df: pd.DataFrame) -> dict:
        """
        完整籌碼面分析
        institutional_df: 三大法人買賣超 DataFrame
        margin_df: 融資融券 DataFrame
        """
        result = {}
        result["institutional"] = self._analyze_institutional(institutional_df)
        result["margin"] = self._analyze_margin(margin_df)
        result["signals"] = self._generate_signals(result)
        result["score"] = self._calc_score(result)
        return result

    # ─── 三大法人分析 ───────────────────────────────────────────

    def _analyze_institutional(self, df: pd.DataFrame) -> dict:
        if df is None or len(df) == 0:
            return {"error": "無三大法人資料"}

        df = df.copy().sort_values("date")

        # 各法人分類
        categories = {
            "Foreign_Investor": "外資",
            "Investment_Trust": "投信",
            "Dealer_self": "自營商(自行)",
            "Dealer_Hedging": "自營商(避險)",
        }

        latest_date = df["date"].max()
        latest = df[df["date"] == latest_date]

        investors = {}
        for eng_key, ch_name in categories.items():
            rows = latest[latest["name"] == eng_key]
            if len(rows) > 0:
                row = rows.iloc[0]
                buy = row.get("buy", 0)
                sell = row.get("sell", 0)
                net = buy - sell
                investors[ch_name] = {
                    "buy": int(buy),
                    "sell": int(sell),
                    "net": int(net),
                }

        # 計算連續買賣天數
        dates = sorted(df["date"].unique())
        for eng_key, ch_name in categories.items():
            cat_df = df[df["name"] == eng_key].sort_values("date")
            if len(cat_df) == 0:
                continue
            cat_df = cat_df.copy()
            cat_df["net"] = cat_df["buy"] - cat_df["sell"]

            consecutive = 0
            direction = None
            for _, row in cat_df.iloc[::-1].iterrows():
                if row["net"] > 0:
                    if direction is None:
                        direction = "買超"
                    if direction == "買超":
                        consecutive += 1
                    else:
                        break
                elif row["net"] < 0:
                    if direction is None:
                        direction = "賣超"
                    if direction == "賣超":
                        consecutive += 1
                    else:
                        break
                else:
                    break

            if ch_name in investors:
                investors[ch_name]["consecutive_days"] = consecutive
                investors[ch_name]["direction"] = direction or "持平"

        # 三大法人合計
        total_net = sum(inv.get("net", 0) for inv in investors.values())

        return {
            "date": str(latest_date.date()) if hasattr(latest_date, "date") else str(latest_date),
            "investors": investors,
            "total_net": total_net,
            "trend": "買超" if total_net > 0 else "賣超" if total_net < 0 else "持平",
        }

    # ─── 融資融券分析 ───────────────────────────────────────────

    def _analyze_margin(self, df: pd.DataFrame) -> dict:
        if df is None or len(df) == 0:
            return {"error": "無融資融券資料"}

        df = df.copy().sort_values("date")
        last = df.iloc[-1]

        # 融資
        margin_buy = int(last.get("MarginPurchaseBuy", 0))
        margin_sell = int(last.get("MarginPurchaseSell", 0))
        margin_balance = int(last.get("MarginPurchaseTodayBalance", 0))
        margin_change = margin_buy - margin_sell

        # 融券
        short_buy = int(last.get("ShortSaleBuy", 0))
        short_sell = int(last.get("ShortSaleSell", 0))
        short_balance = int(last.get("ShortSaleTodayBalance", 0))
        short_change = short_sell - short_buy

        # 券資比
        margin_short_ratio = (
            round(short_balance / margin_balance * 100, 2)
            if margin_balance > 0
            else 0
        )

        # 融資餘額趨勢 (近5日)
        if len(df) >= 5:
            recent = df.tail(5)
            margin_trend = int(
                recent["MarginPurchaseTodayBalance"].iloc[-1]
                - recent["MarginPurchaseTodayBalance"].iloc[0]
            )
        else:
            margin_trend = 0

        return {
            "date": str(last["date"].date()) if hasattr(last["date"], "date") else str(last["date"]),
            "margin_buy": margin_buy,
            "margin_sell": margin_sell,
            "margin_balance": margin_balance,
            "margin_change": margin_change,
            "short_buy": short_buy,
            "short_sell": short_sell,
            "short_balance": short_balance,
            "short_change": short_change,
            "margin_short_ratio": margin_short_ratio,
            "margin_5d_trend": margin_trend,
            "margin_status": "融資增加" if margin_change > 0 else "融資減少",
        }

    # ─── 訊號產生 ───────────────────────────────────────────────

    def _generate_signals(self, result: dict) -> list:
        signals = []
        inst = result.get("institutional", {})
        margin = result.get("margin", {})

        investors = inst.get("investors", {})

        # 外資
        foreign = investors.get("外資", {})
        if foreign.get("direction") == "買超" and foreign.get("consecutive_days", 0) >= 3:
            signals.append(("✅", f"外資連續買超 {foreign['consecutive_days']} 天"))
        elif foreign.get("direction") == "賣超" and foreign.get("consecutive_days", 0) >= 3:
            signals.append(("⚠️", f"外資連續賣超 {foreign['consecutive_days']} 天"))

        # 投信
        trust = investors.get("投信", {})
        if trust.get("direction") == "買超" and trust.get("consecutive_days", 0) >= 3:
            signals.append(("✅", f"投信連續買超 {trust['consecutive_days']} 天"))
        elif trust.get("direction") == "賣超" and trust.get("consecutive_days", 0) >= 3:
            signals.append(("⚠️", f"投信連續賣超 {trust['consecutive_days']} 天"))

        # 三大法人合計
        total_net = inst.get("total_net", 0)
        if total_net > 0:
            signals.append(("✅", f"三大法人合計買超 {total_net:,} 張"))
        elif total_net < 0:
            signals.append(("⚠️", f"三大法人合計賣超 {abs(total_net):,} 張"))

        # 融資
        ratio = margin.get("margin_short_ratio", 0)
        if ratio > 30:
            signals.append(("⚠️", f"券資比偏高 {ratio}%"))

        margin_change = margin.get("margin_change", 0)
        if margin_change > 1000:
            signals.append(("⚠️", f"融資大增 +{margin_change:,} 張"))

        return signals

    # ─── 籌碼面評分 (1-10) ──────────────────────────────────────

    def _calc_score(self, result: dict) -> int:
        score = 5
        inst = result.get("institutional", {})
        margin = result.get("margin", {})

        investors = inst.get("investors", {})

        # 外資
        foreign = investors.get("外資", {})
        if foreign.get("net", 0) > 0:
            score += 1
            if foreign.get("consecutive_days", 0) >= 5:
                score += 1
        elif foreign.get("net", 0) < 0:
            score -= 1
            if foreign.get("consecutive_days", 0) >= 5:
                score -= 1

        # 投信
        trust = investors.get("投信", {})
        if trust.get("net", 0) > 0:
            score += 0.5
        elif trust.get("net", 0) < 0:
            score -= 0.5

        # 融資小 = 好 (散戶少)
        margin_change = margin.get("margin_change", 0)
        if margin_change < -500:
            score += 0.5  # 融資減少 = 籌碼沉澱
        elif margin_change > 1000:
            score -= 0.5  # 融資大增 = 散戶追高

        return max(1, min(10, round(score)))
