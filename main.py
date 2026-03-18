"""
AI 台股分析師 — CLI 入口與 Web Server
用法:
    python main.py                          # 啟動 Web Server (預設)
    python main.py --sync                   # 啟動 Server 並開啟背景自動同步
    python main.py --delay 1.0              # 設定 API 呼叫間隔 (秒)
    python main.py --pause 10.0             # 設定批次間隔 (秒)

    #  CLI 獨立功能
    python main.py --init-cache             # 首次建立全市場快取
    python main.py --update-cache           # 增量更新快取
    python main.py --cache-status           # 查看快取狀態
"""
import os
import sys

# 將 analysis 目錄加入 sys.path 以便直接 import 下面的模組
ANALYSIS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), 'analysis'))
if os.path.exists(ANALYSIS_DIR) and ANALYSIS_DIR not in sys.path:
    sys.path.insert(0, ANALYSIS_DIR)
else:
    # 支援遷移尚在進行中的狀況 (檔案還在根目錄)
    pass

import json
import threading
import time
import argparse
from datetime import datetime

# 嘗試從 analysis 或 根目錄 載入模組
try:
    from ai_analyst import AIAnalyst
    from config import FLASK_HOST, FLASK_PORT, FLASK_DEBUG
    from stock_cache import StockCache
except ImportError as e:
    print(f"模組載入失敗，確認檔案結構是否正確: {e}")
    sys.exit(1)

# === Flask Server 設定 ===
# 設定 template_folder 以便 Flask 能在 analysis/templates 或 templates 找到 HTML
template_dir = os.path.join(ANALYSIS_DIR, 'templates') if os.path.exists(os.path.join(ANALYSIS_DIR, 'templates')) else os.path.join(os.path.abspath(os.path.dirname(__file__)), 'templates')

from flask import Flask, render_template, jsonify, request
app = Flask(__name__, template_folder=template_dir, static_folder=os.path.join(template_dir, 'static') if os.path.exists(os.path.join(template_dir, 'static')) else None)
analyst = None  # lazy init

def background_sync_task(api_delay, batch_delay, use_yfinance=False):
    """背景同步任務：自動偵測並下載缺失資料"""
    mode_label = "yfinance" if use_yfinance else "FinMind"
    print(f"\n🔄 [Background Sync] 啟動 (間隔: {api_delay}s, 批次暫停: {batch_delay}s, 來源: {mode_label})")
    cache = StockCache(api_delay=api_delay, batch_delay=batch_delay, use_yfinance=use_yfinance)
    
    while True:
        try:
            if not cache.is_initialized():
                print("🔄 [Background Sync] 偵測到快取未初始化，開始初步建立...")
                success = cache.init_cache(lookback_days=180)
            else:
                print(f"🔄 [Background Sync] 檢查增量更新... (目前時間: {datetime.now().strftime('%H:%M:%S')})")
                success = cache.update_cache()
            
            if success:
                print("✅ [Background Sync] 同步完成，1 小時後再次檢查。")
                time.sleep(3600)
            else:
                print(f"⏳ [Background Sync] API 額度用完，15 分鐘後重試...")
                time.sleep(900)
        except Exception as e:
            print(f"⚠️ [Background Sync] 發生錯誤: {e}")
            time.sleep(300)

def get_analyst(watchlist=None):
    global analyst
    if analyst is None:
        analyst = AIAnalyst(watchlist=watchlist)
    return analyst

def clean_nan(obj):
    """遞迴清理 NaN / Infinity"""
    import math
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
        return obj
    elif isinstance(obj, dict):
        return {k: clean_nan(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [clean_nan(v) for v in obj]
    return obj

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/analyze", methods=["GET"])
def api_analyze():
    """完整每日分析 API"""
    date = request.args.get("date", None)
    stocks = request.args.get("stocks", None)
    watchlist = [s.strip() for s in stocks.split(",")] if stocks else None

    try:
        a = get_analyst(watchlist)
        if watchlist:
            a.watchlist = watchlist
            result = a.run_daily_analysis(date)
        else:
            result = a.run_full_market_scan(date)
            
        if not result:
            return jsonify({"status": "error", "message": "全市場快取尚未建立，請等待同步完成"}), 500

        return jsonify({"status": "ok", "data": result["html_data"], "text_report": result["text_report"]})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/api/stock/<stock_id>", methods=["GET"])
def api_stock(stock_id):
    """單一股票分析 API"""
    date = request.args.get("date", None)
    try:
        a = get_analyst()
        result = a.analyze_stock(stock_id, date)
        serialized = json.loads(json.dumps(clean_nan(result), default=str))
        return jsonify({"status": "ok", "data": serialized})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/api/download_fundamental", methods=["GET"])
def api_download_fundamental():
    """下載 5 年基本面資料 API"""
    stock_id = request.args.get("stock_id")
    if not stock_id:
        return jsonify({"status": "error", "message": "Missing stock_id"}), 400
    try:
        cache = StockCache()
        res = cache.download_deep_fundamental(stock_id)
        return jsonify({"status": "ok", "data": res})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/api/stock_detail", methods=["GET"])
def api_stock_detail():
    """取得單一股票分析資料 (支援即時補抓)"""
    stock_id = request.args.get("stock_id")
    if not stock_id:
        return jsonify({"status": "error", "message": "Missing stock_id"}), 400
    try:
        cache = StockCache()
        analyst = AIAnalyst()
        result = analyst._analyze_from_cache(cache, stock_id)
        if not result:
            return jsonify({"status": "error", "message": f"找不到 {stock_id} 的資料且補抓失敗"}), 404
        serialized = json.loads(json.dumps(clean_nan(result), default=str))
        return jsonify({"status": "ok", "data": serialized})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/api/watchlist", methods=["GET"])
def api_watchlist():
    """取得分析清單 (限於已有本地資料的股票)"""
    cache = StockCache()
    cached_ids = cache.get_cached_stock_ids()
    stocks = []
    stock_info = cache.load_stock_info()
    for sid in cached_ids:
        name, industry = sid, "未知"
        if stock_info is not None and not stock_info.empty and "stock_id" in stock_info.columns:
            row = stock_info[stock_info["stock_id"] == sid]
            if len(row) > 0:
                name, industry = row.iloc[0]["stock_name"], row.iloc[0]["industry_category"]
        stocks.append({"stock_id": sid, "name": name, "industry": industry})
    return jsonify({"status": "ok", "data": stocks})

# === 主程式邏輯 ===
def main():
    parser = argparse.ArgumentParser(description="AI 台股分析師")
    # Web 伺服器與同步參數
    parser.add_argument("--sync", action="store_true", help="開啟背景自動同步下載")
    parser.add_argument("--delay", type=float, default=0.3, help="API 呼叫間隔 (秒)")
    parser.add_argument("--pause", type=float, default=5.0, help="批次間隔 (秒)")
    # CLI 原有參數
    parser.add_argument("--init-cache", action="store_true", help="首次建立全市場快取")
    parser.add_argument("--days", type=int, default=180, help="初始化快取天數")
    parser.add_argument("--update-cache", action="store_true", help="增量更新快取")
    parser.add_argument("--cache-status", action="store_true", help="查看快取狀態")
    parser.add_argument("--auto-retry", action="store_true", help="額度用完時自動等待並重試")
    parser.add_argument(
        "--yfinance", action="store_true",
        help="日K線改用 yfinance 下載 (FinMind token 額度耗盡時使用，免費且無限制)"
    )

    args = parser.parse_args()

    # == 特殊 CLI 操作 ==
    if args.init_cache:
        cache = StockCache(api_delay=args.delay, batch_delay=args.pause, use_yfinance=args.yfinance)
        while True:
            if cache.init_cache(lookback_days=args.days) or not args.auto_retry: break
            time.sleep(900)
        return

    if args.update_cache:
        cache = StockCache(api_delay=args.delay, batch_delay=args.pause, use_yfinance=args.yfinance)
        while True:
            if cache.update_cache() or not args.auto_retry: break
            time.sleep(900)
        return

    if args.cache_status:
        cache = StockCache()
        if cache.is_initialized(): cache._print_cache_status()
        else: print("❌ 快取尚未初始化，請跑 --init-cache")
        return

    # == 啟動 Web Server (預設任務) ==
    if args.sync:
        threading.Thread(target=background_sync_task, args=(args.delay, args.pause, args.yfinance), daemon=True).start()

    print("\n🚀 AI 台股分析師 Web Server 啟動中...")
    print(f"📡 http://localhost:{FLASK_PORT}")
    if args.sync:
        print("🔄 已開啟背景自動同步功能")
    print("按 Ctrl+C 停止\n")
    app.run(host=FLASK_HOST, port=FLASK_PORT, debug=FLASK_DEBUG)

if __name__ == "__main__":
    main()