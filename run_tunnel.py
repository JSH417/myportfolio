import subprocess
import re
import time
import os

def run():
    cloudflared = os.path.join(os.path.dirname(__file__), "cloudflared.exe")
    url_file = os.path.join(os.path.dirname(__file__), "tunnel_url.txt")
    
    cmd = [cloudflared, "tunnel", "--url", "http://localhost:8000"]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1, encoding="utf-8", errors="replace")

    found_url = False
    start_time = time.time()
    
    while True:
        line = proc.stdout.readline()
        if not line:
            if proc.poll() is not None:
                break
            time.sleep(0.1)
            continue
            
        print(line, end="")
        match = re.search(r'https://[a-zA-Z0-9-]+\.trycloudflare\.com', line)
        if match and not found_url:
            tunnel_url = match.group(0)
            print(f"\n==========================================")
            print(f"★ 나만의 LTE/5G 접속 주소: {tunnel_url}")
            print(f"==========================================\n")
            with open(url_file, "w", encoding="utf-8") as f:
                f.write(tunnel_url)
            found_url = True

if __name__ == "__main__":
    run()
