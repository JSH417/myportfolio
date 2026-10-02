import subprocess
import re
import time
import os
import sys

def start_cloudflare_tunnel(port=8000):
    cloudflared = os.path.join(os.path.dirname(__file__), "cloudflared.exe")
    if not os.path.exists(cloudflared):
        print("cloudflared.exe not found")
        return None

    cmd = [cloudflared, "tunnel", "--url", f"http://localhost:{port}"]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1, encoding="utf-8", errors="replace")

    tunnel_url = None
    start_time = time.time()
    
    # 20초 동안 URL 출력 파싱
    while time.time() - start_time < 20:
        line = proc.stdout.readline()
        if not line:
            continue
        # https://xxxx.trycloudflare.com 형식 매칭
        match = re.search(r'https://[a-zA-Z0-9-]+\.trycloudflare\.com', line)
        if match:
            tunnel_url = match.group(0)
            break

    if tunnel_url:
        # 터널 URL 파일에 저장
        with open(os.path.join(os.path.dirname(__file__), "tunnel_url.txt"), "w", encoding="utf-8") as f:
            f.write(tunnel_url)
        return tunnel_url, proc
    return None, proc

if __name__ == "__main__":
    url, p = start_cloudflare_tunnel(8000)
    if url:
        print(f"TUNNEL_READY: {url}")
        # 계속 대기
        try:
            p.wait()
        except KeyboardInterrupt:
            p.terminate()
    else:
        print("TUNNEL_FAILED")
