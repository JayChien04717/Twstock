"""
AI 台股分析師 — 技術面分析模組
"""
import pandas as pd
import numpy as np
from config import TECHNICAL_PARAMS


class TechnicalAnalysis:
    """K線與技術指標分析"""

    def __init__(self, params: dict = None):
        self.params = params or TECHNICAL_PARAMS

    def analyze(self, df: pd.DataFrame) -> dict:
        """
        完整技術面分析
        df: 日 K 線 DataFrame (需包含 date, open, close, high, low, Trading_Volume)
        """
        if df is None or len(df) < 20:
            return {"error": "資料不足，無法進行技術分析", "score": 5}

        df = df.copy().sort_values("date").reset_index(drop=True)

        result = {
            "ma": self._calc_ma(df),
            "macd": self._calc_macd(df),
            "rsi": self._calc_rsi(df),
            "kd": self._calc_kd(df),
            "bollinger": self._calc_bollinger(df),
            "momentum": self._calc_momentum(df),
            "darvas_box": self._calc_darvas_box(df),
            "latest": self._latest_info(df),
            "history": self._extract_history(df),
        }

        # 綜合訊號與評分
        result["signals"] = self._generate_signals(result)
        result["score"] = self._calc_score(result)

        return result

    # ─── 動能指標 (ROC) ──────────────────────────────────────────

    def _calc_momentum(self, df: pd.DataFrame) -> dict:
        """計算價格變化率 (Rate of Change) 來判斷動能強弱"""
        roc_period_short = self.params.get("roc_short", 10)
        roc_period_long = self.params.get("roc_long", 20)

        roc_short = df["close"].pct_change(periods=roc_period_short) * 100
        roc_long = df["close"].pct_change(periods=roc_period_long) * 100

        latest_roc_short = round(roc_short.iloc[-1], 2) if len(roc_short) > 0 else 0
        latest_roc_long = round(roc_long.iloc[-1], 2) if len(roc_long) > 0 else 0

        # 動能狀態判斷
        if latest_roc_short > 5 and latest_roc_long > 10:
            status = "強勢動能"
        elif latest_roc_short < -5 and latest_roc_long < -10:
            status = "弱勢動能"
        elif latest_roc_short > 0 and latest_roc_long > 0:
            status = "偏多"
        elif latest_roc_short < 0 and latest_roc_long < 0:
            status = "偏空"
        else:
            status = "盤整"

        return {
            "ROC10": latest_roc_short,
            "ROC20": latest_roc_long,
            "status": status,
        }

    # ─── 移動平均線 ─────────────────────────────────────────────

    def _calc_ma(self, df: pd.DataFrame) -> dict:
        ma_data = {}
        for period in self.params["ma_periods"]:
            col = f"MA{period}"
            df[col] = df["close"].rolling(window=period).mean()
            if len(df) >= period:
                ma_data[col] = round(df[col].iloc[-1], 2)
            else:
                ma_data[col] = None

        # 均線排列判斷
        mas = [ma_data.get(f"MA{p}") for p in self.params["ma_periods"]]
        mas_valid = [m for m in mas if m is not None]
        if len(mas_valid) >= 3:
            if all(mas_valid[i] >= mas_valid[i + 1] for i in range(len(mas_valid) - 1)):
                ma_data["arrangement"] = "多頭排列"
            elif all(
                mas_valid[i] <= mas_valid[i + 1] for i in range(len(mas_valid) - 1)
            ):
                ma_data["arrangement"] = "空頭排列"
            else:
                ma_data["arrangement"] = "糾結"
        else:
            ma_data["arrangement"] = "資料不足"

        return ma_data

    # ─── MACD ───────────────────────────────────────────────────

    def _calc_macd(self, df: pd.DataFrame) -> dict:
        fast = self.params["macd_fast"]
        slow = self.params["macd_slow"]
        signal_p = self.params["macd_signal"]

        ema_fast = df["close"].ewm(span=fast, adjust=False).mean()
        ema_slow = df["close"].ewm(span=slow, adjust=False).mean()
        dif = ema_fast - ema_slow
        macd_signal = dif.ewm(span=signal_p, adjust=False).mean()
        osc = (dif - macd_signal) * 2

        latest_dif = round(dif.iloc[-1], 2)
        latest_signal = round(macd_signal.iloc[-1], 2)
        latest_osc = round(osc.iloc[-1], 2)

        # 判斷交叉
        cross = "無"
        if len(dif) >= 2:
            prev_diff = dif.iloc[-2] - macd_signal.iloc[-2]
            curr_diff = dif.iloc[-1] - macd_signal.iloc[-1]
            if prev_diff < 0 and curr_diff > 0:
                cross = "黃金交叉"
            elif prev_diff > 0 and curr_diff < 0:
                cross = "死亡交叉"

        return {
            "DIF": latest_dif,
            "MACD": latest_signal,
            "OSC": latest_osc,
            "cross": cross,
            "trend": "偏多" if latest_dif > latest_signal else "偏空",
        }

    # ─── RSI ────────────────────────────────────────────────────

    def _calc_rsi(self, df: pd.DataFrame) -> dict:
        def rsi(series, period):
            delta = series.diff()
            gain = delta.where(delta > 0, 0).rolling(window=period).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
            rs = gain / loss.replace(0, np.nan)
            return 100 - (100 / (1 + rs))

        rsi_short = rsi(df["close"], self.params["rsi_period_short"])
        rsi_long = rsi(df["close"], self.params["rsi_period_long"])

        rsi6 = round(rsi_short.iloc[-1], 2)
        rsi12 = round(rsi_long.iloc[-1], 2)

        if rsi6 > 80:
            status = "超買"
        elif rsi6 < 20:
            status = "超賣"
        elif rsi6 > 60:
            status = "偏多"
        elif rsi6 < 40:
            status = "偏空"
        else:
            status = "中性"

        return {"RSI6": rsi6, "RSI12": rsi12, "status": status}

    # ─── KD 指標 ────────────────────────────────────────────────

    def _calc_kd(self, df: pd.DataFrame) -> dict:
        period = self.params["kd_period"]
        low_min = df["low"].rolling(window=period).min()
        high_max = df["high"].rolling(window=period).max()

        rsv = ((df["close"] - low_min) / (high_max - low_min)) * 100
        rsv = rsv.fillna(50)

        k = pd.Series(index=df.index, dtype=float)
        d = pd.Series(index=df.index, dtype=float)
        k.iloc[0] = 50
        d.iloc[0] = 50

        for i in range(1, len(df)):
            k.iloc[i] = 2 / 3 * k.iloc[i - 1] + 1 / 3 * rsv.iloc[i]
            d.iloc[i] = 2 / 3 * d.iloc[i - 1] + 1 / 3 * k.iloc[i]

        latest_k = round(k.iloc[-1], 2)
        latest_d = round(d.iloc[-1], 2)

        # 判斷交叉
        cross = "無"
        if len(k) >= 2:
            prev_diff = k.iloc[-2] - d.iloc[-2]
            curr_diff = k.iloc[-1] - d.iloc[-1]
            if prev_diff < 0 and curr_diff > 0:
                cross = "黃金交叉"
            elif prev_diff > 0 and curr_diff < 0:
                cross = "死亡交叉"

        if latest_k > 80:
            status = "超買"
        elif latest_k < 20:
            status = "超賣"
        else:
            status = "中性"

        return {"K": latest_k, "D": latest_d, "cross": cross, "status": status}

    # ─── 布林通道 ───────────────────────────────────────────────

    def _calc_bollinger(self, df: pd.DataFrame) -> dict:
        period = self.params["bollinger_period"]
        std_mult = self.params["bollinger_std"]

        mid = df["close"].rolling(window=period).mean()
        std = df["close"].rolling(window=period).std()
        upper = mid + std_mult * std
        lower = mid - std_mult * std

        latest_close = df["close"].iloc[-1]
        latest_upper = round(upper.iloc[-1], 2)
        latest_mid = round(mid.iloc[-1], 2)
        latest_lower = round(lower.iloc[-1], 2)

        # %B 指標
        bandwidth = (latest_upper - latest_lower) / latest_mid * 100 if latest_mid else 0
        pct_b = (
            (latest_close - latest_lower) / (latest_upper - latest_lower) * 100
            if (latest_upper - latest_lower) != 0
            else 50
        )

        if latest_close > latest_upper:
            position = "突破上軌"
        elif latest_close < latest_lower:
            position = "跌破下軌"
        elif latest_close > latest_mid:
            position = "中軌上方"
        else:
            position = "中軌下方"

        return {
            "upper": latest_upper,
            "mid": latest_mid,
            "lower": latest_lower,
            "bandwidth": round(bandwidth, 2),
            "pct_b": round(pct_b, 2),
            "position": position,
        }

    # ─── 相型理論 (Darvas Box) ──────────────────────────────────
    
    def _calc_darvas_box(self, df: pd.DataFrame) -> dict:
        """
        計算相型理論的箱頂與箱底 (嚴格版 Darvas 演算法)
        邏輯：
        1. 尋找箱頂 (State 1): 創新高後，連續 3 天未突破該高點。
        2. 尋找箱底 (State 2): 箱頂確立後，創低點後連續 3 天未跌穿該低點。
        3. 箱子成型 (State 3): 箱頂/底確立。
           - 若收盤突破箱頂 -> 進入 State 1 (新箱子)
           - 若收盤跌破箱底 -> 進入 State 1 (新箱子，尋找新底部/頂部)
        """
        if len(df) < 20:
            return {"error": "資料不足，無法計算相型"}

        prices = df[["date", "high", "low", "close"]].to_dict('records')
        
        # 狀態機變數
        STATE_SEARCH_TOP = 1
        STATE_SEARCH_BOTTOM = 2
        STATE_BOX_FORMED = 3
        
        state = STATE_SEARCH_TOP
        
        current_top = 0
        current_bottom = float('inf')
        
        days_since_top = 0
        days_since_bottom = 0
        
        active_box_top = None
        active_box_bottom = None
        
        box_history = []  # [{date, top, bottom}] 讓前端畫階梯圖

        for i, row in enumerate(prices):
            high = row["high"]
            low = row["low"]
            close = row["close"]
            date_str = str(row["date"].date()) if hasattr(row["date"], "date") else str(row["date"])
            
            # --- 狀態機更新 ---
            if state == STATE_SEARCH_TOP:
                if high > current_top:
                    current_top = high
                    days_since_top = 0
                else:
                    days_since_top += 1
                    
                if days_since_top >= 3:
                    state = STATE_SEARCH_BOTTOM
                    current_bottom = low
                    days_since_bottom = 0
                    
            elif state == STATE_SEARCH_BOTTOM:
                # 在找箱底的過程中，如果突破箱頂，直接重新找箱頂
                if close > current_top:
                    state = STATE_SEARCH_TOP
                    current_top = high
                    days_since_top = 0
                    continue
                    
                if low < current_bottom:
                    current_bottom = low
                    days_since_bottom = 0
                else:
                    days_since_bottom += 1
                    
                if days_since_bottom >= 3:
                    state = STATE_BOX_FORMED
                    active_box_top = current_top
                    active_box_bottom = current_bottom
                    
            elif state == STATE_BOX_FORMED:
                # 判斷是否突破或跌破
                if close > active_box_top:
                    # 突破，開始找新箱子
                    state = STATE_SEARCH_TOP
                    current_top = high
                    days_since_top = 0
                    active_box_top = None
                    active_box_bottom = None
                elif close < active_box_bottom:
                    # 跌破，停損，重新找箱子
                    state = STATE_SEARCH_TOP
                    current_top = high
                    days_since_top = 0
                    active_box_top = None
                    active_box_bottom = None

            # --- 記錄歷史軌跡 (只記錄已成型的箱子) ---
            box_history.append({
                "date": date_str,
                "top": active_box_top,
                "bottom": active_box_bottom
            })

        latest_close = prices[-1]["close"]
        
        # 決定當前趨勢
        if active_box_top is not None and active_box_bottom is not None:
             trend = "箱型整理"
             buy_price = f"{active_box_bottom * 1.01:.2f} ~ {active_box_bottom * 1.03:.2f}"
             sell_price = f"{active_box_top * 0.97:.2f} ~ {active_box_top * 0.99:.2f} (跌破 {active_box_bottom} 停損)"
             reason = f"成功建立 Darvas Box，區間為 {active_box_bottom} ~ {active_box_top}，目前在箱內震盪中。建議在接近箱底買入，箱頂賣出；若跌破箱底必須嚴格停損。"
        else:
             # 如果目前不在成型的箱子中，看前一個成型的箱子狀態
             # 找最後一個成型的箱子
             last_formed_top = None
             last_formed_bottom = None
             for hist in reversed(box_history):
                 if hist["top"] is not None:
                     last_formed_top = hist["top"]
                     last_formed_bottom = hist["bottom"]
                     break
                     
             if last_formed_top and latest_close > last_formed_top:
                 trend = "強勢突破"
                 buy_price = f"現價 ({latest_close}) 附近"
                 sell_price = f"{last_formed_top} (跌破前高停損)"
                 reason = f"股價強勢突破前一個 Darvas Box ({last_formed_top})，新箱子尚未成型。此時屬於動能突破階段，可順勢做多，並以舊箱頂作為防守停損點。"
             elif last_formed_bottom and latest_close < last_formed_bottom:
                 trend = "弱勢跌破"
                 buy_price = "暫不建議買進"
                 sell_price = f"反彈至 {last_formed_bottom} 附近賣出"
                 reason = f"股價跌破前一個 Darvas Box ({last_formed_bottom})，趨勢轉弱。在新的底部確立(新箱子成型)前，建議空手觀望或反彈減碼。"
             else:
                 trend = "新箱型建構中"
                 buy_price = "等待箱底確立"
                 sell_price = "等待箱頂確立"
                 reason = "股價正在摸索新的支撐與壓力，尚未滿足 Darvas 3 日不破之規則。建議等待新箱體完全確立後再行動。"

        return {
            "current_top": active_box_top,
            "current_bottom": active_box_bottom,
            "trend": trend,
            "buy_price": buy_price,
            "sell_price": sell_price,
            "reason": reason,
            "history": box_history[-180:] # 與 K 線圖預設長度同步
        }

    # ─── 最新資訊 ───────────────────────────────────────────────

    def _latest_info(self, df: pd.DataFrame) -> dict:
        last = df.iloc[-1]
        prev = df.iloc[-2] if len(df) >= 2 else last

        change = last["close"] - prev["close"]
        change_pct = (change / prev["close"] * 100) if prev["close"] else 0

        # 成交量變化
        vol_ma5 = df["Trading_Volume"].tail(5).mean()
        vol_ratio = last["Trading_Volume"] / vol_ma5 if vol_ma5 > 0 else 1

        return {
            "date": str(last["date"].date()) if hasattr(last["date"], "date") else str(last["date"]),
            "open": last["open"],
            "high": last["high"],
            "low": last["low"],
            "close": last["close"],
            "volume": int(last["Trading_Volume"]),
            "change": round(change, 2),
            "change_pct": round(change_pct, 2),
            "vol_ratio": round(vol_ratio, 2),
            "vol_status": "爆量" if vol_ratio > 2 else "量增" if vol_ratio > 1.3 else "量縮" if vol_ratio < 0.7 else "正常",
        }

    # ─── 歷史 K 線與均線 (前端畫圖用) ───────────────────────────────────────────────

    def _extract_history(self, df: pd.DataFrame, days: int = 180) -> list:
        """抽取給前端畫圖用的歷史資料 (K線 + 均線 + 成交量)"""
        if len(df) == 0:
            return []
        
        recent = df.tail(days).copy()
        recent = recent.replace({np.nan: None})
        
        history = []
        for _, row in recent.iterrows():
            date_str = str(row["date"].date()) if hasattr(row["date"], "date") else str(row["date"])
            item = {
                "date": date_str,
                "open": row["open"],
                "high": row["high"],
                "low": row["low"],
                "close": row["close"],
                "volume": int(row["Trading_Volume"]) if row.get("Trading_Volume") is not None else 0
            }
            for p in self.params.get("ma_periods", [5, 10, 20, 60]):
                col = f"MA{p}"
                item[col] = row.get(col)
                
            history.append(item)
            
        return history

    # ─── 訊號產生 ───────────────────────────────────────────────

    def _generate_signals(self, result: dict) -> list:
        signals = []
        ma = result.get("ma", {})
        macd = result.get("macd", {})
        rsi = result.get("rsi", {})
        kd = result.get("kd", {})
        boll = result.get("bollinger", {})
        momentum = result.get("momentum", {})
        latest = result.get("latest", {})

        if ma.get("arrangement") == "多頭排列":
            signals.append(("✅", "均線多頭排列"))
        elif ma.get("arrangement") == "空頭排列":
            signals.append(("⚠️", "均線空頭排列"))

        if macd.get("cross") == "黃金交叉":
            signals.append(("✅", "MACD 黃金交叉"))
        elif macd.get("cross") == "死亡交叉":
            signals.append(("⚠️", "MACD 死亡交叉"))

        if rsi.get("status") == "超買":
            signals.append(("⚠️", f"RSI 超買 ({rsi.get('RSI6')})"))
        elif rsi.get("status") == "超賣":
            signals.append(("✅", f"RSI 超賣 ({rsi.get('RSI6')})"))

        if kd.get("cross") == "黃金交叉":
            signals.append(("✅", "KD 黃金交叉"))
        elif kd.get("cross") == "死亡交叉":
            signals.append(("⚠️", "KD 死亡交叉"))

        if boll.get("position") == "突破上軌":
            signals.append(("⚠️", "突破布林上軌 (注意回檔)"))
        elif boll.get("position") == "跌破下軌":
            signals.append(("✅", "跌破布林下軌 (可能反彈)"))

        # 動能訊號
        if momentum.get("status") == "強勢動能":
            signals.append(("🚀", "動能強勁 (ROC>10%)"))
        elif momentum.get("status") == "弱勢動能":
            signals.append(("⚠️", "動能疲弱 (ROC<-10%)"))

        if latest.get("vol_status") == "爆量":
            signals.append(("🔔", f"成交量爆量 ({latest.get('vol_ratio')}x)"))

        return signals

    # ─── 技術面評分 (1-10) ──────────────────────────────────────

    def _calc_score(self, result: dict) -> int:
        score = 5.0  # 基準分

        ma = result.get("ma", {})
        macd = result.get("macd", {})
        rsi = result.get("rsi", {})
        kd = result.get("kd", {})
        momentum = result.get("momentum", {})

        # 均線
        if ma.get("arrangement") == "多頭排列":
            score += 1.5
        elif ma.get("arrangement") == "空頭排列":
            score -= 1.5

        # MACD
        if macd.get("trend") == "偏多":
            score += 0.5
        else:
            score -= 0.5
        if macd.get("cross") == "黃金交叉":
            score += 1.0
        elif macd.get("cross") == "死亡交叉":
            score -= 1.0

        # RSI
        rsi6 = rsi.get("RSI6", 50)
        if 40 <= rsi6 <= 60:
            pass  # 中性
        elif rsi6 > 70:
            score -= 0.5
        elif rsi6 < 30:
            score += 0.5

        # KD
        if kd.get("cross") == "黃金交叉":
            score += 1.0
        elif kd.get("cross") == "死亡交叉":
            score -= 1.0

        # 動能
        if momentum.get("status") == "強勢動能":
            score += 1.0
        elif momentum.get("status") == "弱勢動能":
            score -= 1.0
        elif momentum.get("status") == "偏多":
            score += 0.5
        elif momentum.get("status") == "偏空":
            score -= 0.5

        score = max(0.0, min(10.0, score))
        return int(round(score))
