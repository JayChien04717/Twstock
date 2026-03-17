import sys
import traceback
from datetime import datetime, timedelta
from stock_cache import StockCache

try:
    print("Testing full pipeline for 2330...")
    cache = StockCache()
    sid = '2330'
    start = (datetime.now() - timedelta(days=90)).strftime('%Y-%m-%d')
    start_rev = (datetime.now() - timedelta(days=400)).strftime('%Y-%m-%d')
    end = datetime.now().strftime('%Y-%m-%d')

    print('Downloading price...')
    df = cache.fetcher.get_daily_price(sid, start, end)
    cache._append_to_existing('daily_price.csv', [df])
    
    print('Downloading inst...')
    df = cache.fetcher.get_institutional(sid, start, end)
    cache._append_to_existing('institutional.csv', [df])
    
    print('Downloading margin...')
    df = cache.fetcher.get_margin(sid, start, end)
    cache._append_to_existing('margin.csv', [df])
    
    print('Downloading per...')
    df = cache.fetcher.get_per_pbr(sid, start, end)
    cache._append_to_existing('per_pbr.csv', [df])
    
    print('Downloading rev...')
    df = cache.fetcher.get_revenue(sid, start_rev, end)
    cache._append_to_existing('revenue.csv', [df])
    
    print('Downloading fin...')
    df = cache.fetcher.get_financial(sid, start_rev, end)
    cache._append_to_existing('financial.csv', [df])
    
    print('Success!')
except Exception as e:
    traceback.print_exc(file=sys.stdout)
