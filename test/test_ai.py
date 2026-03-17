import sys
import traceback
from ai_analyst import AIAnalyst

try:
    print("Testing analyze_stock('2330')...")
    a = AIAnalyst()
    res = a.analyze_stock("2330")
    print(res.keys())
except Exception as e:
    traceback.print_exc(file=sys.stdout)
