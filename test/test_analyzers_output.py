import sys
import os

# 將 analysis 目錄加入 sys.path
ANALYSIS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "analysis"))
if ANALYSIS_DIR not in sys.path:
    sys.path.insert(0, ANALYSIS_DIR)

from short_term_analyzer import ShortTermAnalyzer
from mid_term_analyzer import MidTermAnalyzer
from long_term_analyzer import LongTermAnalyzer

def test_analyzers():
    mock_tech = {
        "latest": {"close": 100, "change_pct": 5, "vol_status": "爆量", "vol_ratio": 2.5},
        "ma": {"MA5": 98, "MA10": 95, "MA20": 92, "arrangement": "多頭排列"},
        "bollinger": {"upper": 105, "mid": 98, "lower": 91, "position": "中軌上方"},
        "kd": {"cross": "黃金交叉", "K": 70, "D": 60},
        "rsi": {"RSI6": 65, "status": "偏多"},
        "momentum": {"status": "強勢動能"},
        "darvas_box": {"trend": "強勢突破", "current_top": 95, "current_bottom": 85, "buy_price": "96", "sell_price": "105", "reason": "突破箱頂"}
    }
    
    mock_chip = {
        "institutional": {
            "investors": {
                "外資": {"net": 1000, "consecutive_days": 3},
                "投信": {"net": 500, "consecutive_days": 2}
            },
            "trend": "同步買超"
        }
    }
    
    mock_fund = {
        "valuation": {"PER": 15, "status": "合理", "per_percentile": 45, "dividend_yield": 4.5},
        "revenue": {"yoy": 15},
        "financial": {"eps": 6.5},
        "score": 7
    }

    print("--- Short Term Analyzer ---")
    short = ShortTermAnalyzer()
    res_short = short.analyze(mock_tech, mock_chip)
    print(f"Action: {res_short['action']}")
    print(f"Buy: {res_short['buy_range']}")
    print(f"Sell: {res_short['sell_range']}")
    print(f"Basis: {res_short['price_basis']}")
    assert "buy_range" in res_short
    assert "sell_range" in res_short
    assert "price_basis" in res_short

    print("\n--- Mid Term Analyzer ---")
    mid = MidTermAnalyzer()
    res_mid = mid.analyze(mock_tech, mock_chip)
    print(f"Action: {res_mid['action']}")
    print(f"Buy: {res_mid['buy_range']}")
    print(f"Sell: {res_mid['sell_range']}")
    print(f"Basis: {res_mid['price_basis']}")
    assert "buy_range" in res_mid
    assert "sell_range" in res_mid
    assert "price_basis" in res_mid

    print("\n--- Long Term Analyzer ---")
    long = LongTermAnalyzer()
    res_long = long.analyze(mock_fund, mock_tech)
    print(f"Action: {res_long['action']}")
    print(f"Buy: {res_long['buy_range']}")
    print(f"Sell: {res_long['sell_range']}")
    print(f"Basis: {res_long['price_basis']}")
    assert "buy_range" in res_long
    assert "sell_range" in res_long
    assert "price_basis" in res_long

    print("\n✅ All tests passed!")

if __name__ == "__main__":
    test_analyzers()
