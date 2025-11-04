# app.py
import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import requests
from bs4 import BeautifulSoup
from io import StringIO
import time

st.set_page_config(page_title="📈 KOSPI200 추천 시스템", layout="wide", page_icon="📊")
st.title("📈 코스피200 추천 시스템 — 초보자용")

st.markdown("""
간단한 규칙 기반 추천(모멘텀 + 변동성 + 이동평균)과 시각화를 제공합니다.  
원하면 알고리즘(가중치·기간)을 바꿔서 실험해보자.
""")

# ---------- 헬퍼: Yahoo KOSPI200 구성 종목 시도적 가져오기 ----------
@st.cache_data(ttl=60*60)
def fetch_ks200_components_from_yahoo():
    """
    시도: Yahoo Finance 지수 컴포넌트 페이지를 크롤링해서 ticker list 얻기.
    (동작 불가 시 None 반환 — 사용자 CSV 업로드 사용)
    """
    url = "https://finance.yahoo.com/quote/%5EKS200/components/"
    try:
        r = requests.get(url, timeout=10, headers={"User-Agent":"Mozilla/5.0"})
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        # Yahoo 페이지에 초기화 데이터가 스크립트에 JSON으로 들어있음 -> 찾기
        scripts = soup.find_all("script")
        for s in scripts:
            txt = s.string
            if not txt:
                continue
            if "root.App.main" in txt:
                start = txt.find("root.App.main") 
                # 간단 파싱: JSON 부분 추출
                json_part = txt[txt.find("root.App.main")+14: txt.rfind(";\n")]
                # 작은 포맷 차이로 실패 가능 -> 안전하게 None 반환
                break
        # If we reach here, best-effort fallback: try GET components API via Yahoo (unstable)
        # Instead of complex parsing, attempt the page with query params that sometimes return JSON
        return None
    except Exception:
        return None

# ---------- 사용자 입력: 구성 종목 CSV 업로드 또는 자동 시도 ----------
st.sidebar.header("데이터 소스")
st.sidebar.write("KOSPI200 구성 종목을 자동으로 가져오려 시도합니다. 안 되면 CSV 업로드하세요.")
use_auto = st.sidebar.checkbox("Yahoo에서 자동 시도", value=True)
uploaded = st.sidebar.file_uploader("또는 KOSPI200 티커(csv, 한 열에 티커 ex: 005930.KS)", type=["csv","txt"])

tickers = None
if uploaded is not None:
    try:
        s = StringIO(uploaded.getvalue().decode("utf-8"))
        df_in = pd.read_csv(s, header=None)
        tickers = df_in.iloc[:,0].astype(str).tolist()
    except Exception:
        st.sidebar.error("CSV 파싱 실패 — 파일 형식 확인")
elif use_auto:
    with st.spinner("Yahoo에서 KOSPI200 구성 시도 중..."):
        comps = fetch_ks200_components_from_yahoo()
        if comps:
            tickers = comps
        else:
            st.sidebar.info("자동 수집 실패 시, CSV 업로드를 권장합니다. (Yahoo 페이지 구조 변화 가능)")

# 간단 안내
st.sidebar.markdown("---")
st.sidebar.markdown("참고: yfinance로 데이터 불러옵니다. 한국 종목은 '005930.KS' 형식으로 표기.")

# ---------- 사용자 설정 ----------
st.sidebar.header("추천 설정")
top_n = st.sidebar.slider("추천 종목 수 (Top N)", 1, 50, 10)
lookback_days = st.sidebar.slider("모멘텀 기간 (일)", 30, 252, 90)
vol_window = st.sidebar.slider("변동성 산정(window, 일)", 20, 120, 60)
short_ma = st.sidebar.number_input("단기 MA (일)", min_value=2, max_value=100, value=20)
long_ma = st.sidebar.number_input("장기 MA (일)", min_value=10, max_value=300, value=60)
refresh_btn = st.sidebar.button("데이터 새로 가져오기")

# ---------- 메인: 데이터 로드 & 계산 ----------
if not tickers:
    st.info("왼쪽에서 구성종목을 불러오거나 CSV를 업로드해주세요.")
    st.stop()

# normalize tickers: if user uploaded numeric codes like 005930, add .KS if absent
def normalize(t):
    t = t.strip()
    if t.endswith(".KS") or t.endswith(".KQ"):
        return t
    if t.isdigit() and len(t) == 6:
        return t + ".KS"
    return t

tickers = [normalize(t) for t in tickers]
# limit to reasonable number to avoid yfinance throttling (KOSPI200=200 normally)
MAX_FETCH = 250
if len(tickers) > MAX_FETCH:
    tickers = tickers[:MAX_FETCH]

st.write(f"데이터를 불러올 종목 수: {len(tickers)}")

@st.cache_data(ttl=60*30)
def download_prices(tickers, period="1y", interval="1d"):
    # yfinance supports list download
    data = yf.download(tickers, period=period, interval=interval, group_by='ticker', auto_adjust=True, threads=True)
    return data

# 친절 모드: 진행 상태 표시
with st.spinner("주가 데이터 불러오는 중... (몇 분 걸릴 수 있음)"):
    data = download_prices(tickers, period="1y", interval="1d")

# 데이터 정리 & 지표 계산
results = []
failed = []
for sym in tickers:
    try:
        # If multiple tickers, yfinance returns multiindex; handle both cases
        if len(tickers) == 1:
            df = data.copy()
        else:
            if sym not in data.columns.get_level_values(0):
                # sometimes symbol missing
                failed.append(sym)
                continue
            df = data[sym].copy()
        if df.empty:
            failed.append(sym)
            continue
        close = df['Close'].dropna()
        if close.shape[0] < max(long_ma, vol_window) + 5:
            failed.append(sym)
            continue

        ret = (close.iloc[-1] / close.iloc[-lookback_days] - 1) if len(close) > lookback_days else np.nan
        vol = close.pct_change().rolling(window=vol_window).std().iloc[-1]
        ma_short = close.rolling(window=short_ma).mean().iloc[-1]
        ma_long = close.rolling(window=long_ma).mean().iloc[-1]
        golden = 1 if ma_short > ma_long else 0

        # simple score: normalized momentum rank + inverse vol + MA bonus
        results.append({
            "ticker": sym,
            "price": float(close.iloc[-1]),
            "momentum": float(ret) if pd.notna(ret) else np.nan,
            "volatility": float(vol) if pd.notna(vol) else np.nan,
            "ma_short": float(ma_short),
            "ma_long": float(ma_long),
            "ma_golden": golden
        })
    except Exception:
        failed.append(sym)

df_res = pd.DataFrame(results).dropna(subset=["momentum","volatility"])
if df_res.empty:
    st.error("유효한 종목 데이터가 없습니다. CSV나 다른 데이터 소스를 확인하세요.")
    st.stop()

# normalize ranks
df_res["mom_rank"] = df_res["momentum"].rank(ascending=False)
df_res["vol_rank"] = df_res["volatility"].rank(ascending=True)  # 낮은 변동성 순이 좋은 것
# score: mom_rank weight 0.6, vol_rank weight 0.3, ma_golden bonus  - smaller is better so invert ranks
df_res["score"] = ( ( (len(df_res) - df_res["mom_rank"]) / len(df_res) ) * 0.6
                  + ( (len(df_res) - df_res["vol_rank"]) / len(df_res) ) * 0.3
                  + df_res["ma_golden"] * 0.1 )
df_res = df_res.sort_values("score", ascending=False).reset_index(drop=True)

# ---------- 출력: 추천 리스트 ----------
st.subheader("추천 Top (간단)")
st.write(f"기준: 최근 {lookback_days}일 모멘텀 ↑  |  변동성 ↓  |  단기/장기 MA 골든크로스 보너스")
st.dataframe(df_res[["ticker","price","momentum","volatility","ma_golden","score"]].head(top_n).style.format({
    "price":"{:.2f}",
    "momentum":"{:.4f}",
    "volatility":"{:.4f}",
    "score":"{:.4f}"
}))

# ---------- 개별 종목 상세 조회 ----------
st.subheader("개별 종목 상세 조회")
sym_sel = st.selectbox("종목 선택", df_res["ticker"].tolist())
if sym_sel:
    st.write("### 시계열(최근 1년)")
    # plot price
    if len(tickers) == 1:
        df = data.copy()
    else:
        df = data[sym_sel].copy()
    close = df['Close'].dropna()
    st.line_chart(close)

    st.write("### 주요 지표")
    row = df_res[df_res["ticker"] == sym_sel].iloc[0]
    st.metric("현재가", f"{row['price']:.2f} KRW")
    st.metric("최근 모멘텀", f"{row['momentum']:.4f}")
    st.metric("변동성(σ)", f"{row['volatility']:.4f}")
    st.write("MA 단기:", int(short_ma), " —", f"{row['ma_short']:.2f}")
    st.write("MA 장기:", int(long_ma), " —", f"{row['ma_long']:.2f}")
    st.write("골든크로스(단기>장기):", "예" if row['ma_golden'] else "아니오")

# ---------- 실패/로그 ----------
if failed:
    with st.expander("데이터 로드 실패 또는 제외된 티커"):
        st.write(failed)
