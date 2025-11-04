# 📈 KOSPI200 추천 시스템 (Streamlit)

초보자도 이해하기 쉬운 규칙 기반 주식 추천 도구입니다.
- 데이터 소스: Yahoo Finance (yfinance) — 한국 티커는 `005930.KS` 같은 형식 사용.
- 추천 기준: 모멘텀(최근 수익률) + 변동성 필터 + 이동평균 골든크로스

## 실행
```bash
git clone <repo>
cd repo
pip install -r requirements.txt
streamlit run app.py
