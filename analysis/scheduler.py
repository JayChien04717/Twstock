import time
import subprocess
import sys
import os

def main():
    # 預設等一小時 (3600秒)
    delay = 3600 
    if len(sys.argv) > 1:
        try:
            delay = int(sys.argv[1])
        except ValueError:
            print(f"無效的延遲參數: {sys.argv[1]}, 使用預設 3600 秒")

    print(f"⏰ 排程啟動：將在 {delay} 秒 ({(delay/3600):.1f} 小時) 後開始同步資料...")
    
    # 倒數計時顯示 (可選)
    # for i in range(delay, 0, -60):
    #     print(f"\r⏳ 剩餘時間: {i//60} 分鐘", end="")
    #     time.sleep(min(i, 60))
    
    time.sleep(delay)
    
    print("\n🚀 時間到！啟動快取同步...")
    
    # 使用當前環境的 python 執行 main.py --init-cache
    python_exe = sys.executable
    cmd = [python_exe, "main.py", "--init-cache"]
    
    # 傳透其他參數 (例如 --delay, --pause)
    if len(sys.argv) > 2:
        cmd.extend(sys.argv[2:])
    
    try:
        # 執行並實時顯示輸出
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8")
        for line in process.stdout:
            print(line, end="")
        process.wait()
        
        if process.returncode == 0:
            print("\n✅ 資料同步完成！")
        else:
            print(f"\n❌ 同步結束，結束代碼: {process.returncode}")
            
    except Exception as e:
        print(f"\n❌ 執行失敗: {e}")

if __name__ == "__main__":
    main()
