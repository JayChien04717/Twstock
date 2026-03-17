import sys
import traceback
from data_fetcher import StockDataFetcher

try:
    f = StockDataFetcher()
    print("Testing get_margin...", flush=True)
    f.get_margin("2330", "2024-01-01", "2024-05-01")
except Exception as e:
    traceback.print_exc(file=sys.stdout)
