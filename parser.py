import os
import json
import re
from typing import List, Dict, Any

# Google GenAI SDK (google-genai 패키지 설치됨)
try:
    from google import genai
    from google.genai import types
except ImportError:
    genai = None

PROMPT_OCR_PORTFOLIO = """
너는 금융/주식 계좌 스크린샷 및 매매내역 전문 파서(Parser)이다.
주어진 증권사(토스증권, 키움증권, 한국투자증권, 미래에셋, KB증권 등) 화면 캡처 또는 텍스트에서 
[보유 종목, ETF, 주식, 외화 RP, 달러 예수금, 원화 현금] 정보를 추출하여 순수 JSON 목록으로 반환하라.

반드시 지켜야 할 규칙:
1. 결과는 반드시 JSON 배열이어야 한다. 마크다운(```json) 태그 없이 JSON만 출력하라.
2. 각 항목의 JSON 필드 규격:
   - "symbol": 종목코드(티커). 한국 종목은 6자리 숫자(예: '069500', '379800'), 미국 종목은 영문 티커('VOO', 'QQQ', 'SCHD'), 달러RP/외화예수금은 'USD_RP' 또는 'CASH_USD'
   - "name": 종목 또는 자산명 (예: 'KODEX 200', 'TIGER 미국배당다우존스', 'Vanguard S&P 500', '외화RP', '달러예수금')
   - "asset_type": 다음 중 하나여야 함 ['KR_ETF', 'US_ETF', 'USD_RP', 'CASH_USD', 'CASH_KRW']
   - "currency": 'KRW' 또는 'USD'
   - "quantity": 보유 수량 (실수 또는 정수). 외화 RP의 경우 보유 달러 금액($).
   - "avg_price": 매입 단가 / 평단가 (KRW 종목은 원화, USD 종목은 달러, RP는 1.0)
   - "current_price": 현재가 또는 평가단가 (화면에 표시되어 있다면)

3. 달러 RP(외화 RP), 외화 CMM/예수금 등의 자산도 절대 누락하지 말고 반드시 포함하라.
"""

def _call_gemini(client, contents):
    # Google AI의 최신 지원 모델들을 순차적으로 시도
    candidate_models = [
        'gemini-3.8-flash',
        'gemini-3.5-flash-lite',
        'gemini-2.5-flash',
        'gemini-2.0-flash'
    ]
    last_err = None
    for m in candidate_models:
        try:
            return client.models.generate_content(model=m, contents=contents)
        except Exception as e:
            last_err = e
            continue
    raise last_err

def parse_portfolio_image(image_bytes: bytes, mime_type: str = "image/jpeg", api_key: str = None) -> List[Dict[str, Any]]:
    """
    Gemini Vision API를 활용하여 계좌 캡처 이미지에서 자산 리스트(JSON)를 추출
    """
    key = api_key or os.getenv("GEMINI_API_KEY")
    if not key:
        return {"error": "GEMINI_API_KEY가 설정되지 않았습니다. .env 파일이나 설정 화면에 API 키를 입력해주세요."}

    if not genai:
        return {"error": "google-genai 모듈이 설치되어 있지 않습니다."}

    try:
        client = genai.Client(api_key=key)
        response = _call_gemini(
            client,
            contents=[
                types.Part.from_bytes(
                    data=image_bytes,
                    mime_type=mime_type,
                ),
                PROMPT_OCR_PORTFOLIO
            ]
        )
        text = response.text.strip()
        # ```json ... ``` 제거
        text = re.sub(r'^```json\s*', '', text)
        text = re.sub(r'\s*```$', '', text)
        data = json.loads(text)
        return data
    except Exception as e:
        return {"error": f"이미지 인식 분석 중 오류 발생: {str(e)}"}

def parse_trade_text(text: str, api_key: str = None) -> List[Dict[str, Any]]:
    """
    카카오톡 체결 문자 또는 텍스트 거래내역 파싱
    """
    key = api_key or os.getenv("GEMINI_API_KEY")
    if not key:
        # 규칙 기반 간단한 정규식 추출 시도
        return parse_text_fallback(text)

    try:
        client = genai.Client(api_key=key)
        prompt = f"""
        다음 주식/ETF/외화RP 매매 체결 문자 또는 내역 텍스트를 분석하여 JSON 배열로 반환하라.
        {PROMPT_OCR_PORTFOLIO}
        
        입력 텍스트:
        {text}
        """
        response = _call_gemini(client, contents=prompt)
        raw = response.text.strip()
        raw = re.sub(r'^```json\s*', '', raw)
        raw = re.sub(r'\s*```$', '', raw)
        return json.loads(raw)
    except Exception:
        return parse_text_fallback(text)

def parse_text_fallback(text: str) -> List[Dict[str, Any]]:
    """정규식 기본 파서 (Gemini API 키 미입력 시 대비)"""
    results = []
    # 외화 RP 패턴 감지
    rp_match = re.search(r'(외화\s*RP|달러\s*RP|USD\s*RP).*?([0-9,.]+)\s*(달러|\$|USD)', text, re.IGNORECASE)
    if rp_match:
        qty = float(rp_match.group(2).replace(",", ""))
        results.append({
            "symbol": "USD_RP",
            "name": "외화 RP",
            "asset_type": "USD_RP",
            "currency": "USD",
            "quantity": qty,
            "avg_price": 1.0,
            "current_price": 1.0
        })
    return results
