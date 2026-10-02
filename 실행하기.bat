@echo off
chcp 65001 > nul
title ETF & 달러RP 포트폴리오 관리자 (원클릭 실행)
echo =================================================================
echo        ETF & 외화RP 올인원 포트폴리오 (LTE/5G 외부 접속 지원)
echo =================================================================
echo.

cd /d "%~dp0"

echo [1/3] 기존 실행 프로세스 정리 중...
taskkill /f /im python.exe 2>nul
taskkill /f /im cloudflared.exe 2>nul

echo [2/3] 백엔드 서버 시작 중...
start /b python app.py

timeout /t 2 > nul

echo [3/3] Cloudflare 보안 터널 연결 중 (외부 어디서나 접속 가능)...
start /b python run_tunnel.py

timeout /t 5 > nul

set /p TUNNEL_URL=<tunnel_url.txt

echo.
echo =================================================================
echo  ★ 서버 및 외부 인터넷 터널이 성공적으로 열렸습니다!
echo.
echo  [1] PC 로컬 접속 주소     : http://localhost:8000
echo  [2] 집안 Wi-Fi 모바일 주소: http://192.168.219.111:8000
echo.
echo  [3] ★ 전세계 어디서나 (LTE/5G/외부):
echo      %TUNNEL_URL%
echo =================================================================
echo.
echo [안내] 스마트폰(LTE/5G)에서 위 3번 주소로 접속한 후
echo        "홈 화면에 추가"를 누르면 앱스토어 어플처럼 작동합니다!
echo.

start http://localhost:8000

echo 서버를 종료하려면 이 창에서 아무 키나 누르세요.
pause > nul

taskkill /f /im python.exe 2>nul
taskkill /f /im cloudflared.exe 2>nul
