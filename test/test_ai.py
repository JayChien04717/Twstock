import sys
import os
import traceback
sys.path.insert(0, os.path.abspath('./analysis'))

try:
    from ai_analyst import AIAnalyst
    print("Testing analyze_stock('2722')...")
    a = AIAnalyst()
    res = a.analyze_stock("2722")
    if "advice" in res:
        import json
        print(json.dumps(res["advice"], indent=2, ensure_ascii=False))
    else:
        print("Keys:", res.keys())
except Exception as e:
    traceback.print_exc(file=sys.stdout)
