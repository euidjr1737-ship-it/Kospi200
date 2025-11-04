import streamlit as st
import pandas as pd
import yfinance as yf

st.set_page_config(page_title="📈 코스피200 주식 추천 시스템", page_icon="💹")

st.title("📈 코스피200 주식 추천 시스템")
st.write("초보자도 쉽게 이해할 수 있는 주식 분석 도구입니다. 💡")

# 코스피200 대표 종목 리스트 (일부 샘플)
kospi200 = {
    "삼성전자": "005930.KS",
    "LG에너지솔루션": "373220.KS",
    "SK하이닉스": "000660.KS",
    "NAVER": "035420.KS",
    "현대차": "005380.KS",
    "카카오": "035720.KS",
    "셀트리온": "068270.KS",
    "POSCO홀딩스": "005490.KS",
}

# --- 선택 UI
option = st.selectbox("🔍 분석할 코스피200 종목을 선택하세요:", list(kospi200.keys()))

if option:
    ticker = kospi200[option]
    data = yf.download(ticker, period="6mo")

    if not data.empty:
        st.subheader(f"📊 {option} ({ticker}) 주가 추이")
        st.line_chart(data["Close"])

        st.write("📅 최근 5일 요약")
        st.dataframe(data.tail())

        # --- 간단한 추천 로직
        current_price = data["Close"].iloc[-1]
        ma20 = data["Close"].rolling(window=20).mean().iloc[-1]

        st.divider()
        st.subheader("💬 투자 추천 요약")

        if current_price > ma20:
            st.success(f"📈 현재 주가는 20일 이동평균선보다 높습니다. 상승 추세로 판단할 수 있습니다.")
        else:
            st.warning(f"📉 현재 주가는 20일 이동평균선보다 낮습니다. 하락 추세일 수 있습니다.")

        st.caption("※ 본 분석은 단순 참고용이며, 실제 투자 판단은 신중히 하세요.")
    else:
        st.error("데이터를 불러올 수 없습니다. 종목 코드를 확인하세요.")
