"""
투자 정보 터미널 (Streamlit)
- 좌측 대분류/중분류 메뉴 구조
- 무료 API/공개 RSS만 사용
- MENU 딕셔너리에 항목만 추가하면 메뉴가 늘어나는 확장형 구조
"""

import streamlit as st
import pandas as pd
import requests
import feedparser
from datetime import datetime

# ─────────────────────────────────────────────
# 페이지 기본 설정 (블룸버그 스타일 다크테마)
# ─────────────────────────────────────────────
st.set_page_config(page_title="TERMINAL", layout="wide", page_icon="📊")

st.markdown("""
<style>
.stApp { background-color:#000000; color:#e8e8e8; font-family:'IBM Plex Mono',monospace; }
section[data-testid="stSidebar"] { background-color:#0a0a0a; border-right:1px solid #242424; }
h1,h2,h3 { color:#ff9f1c !important; }
.stDataFrame { background-color:#0a0a0a; }
div[data-baseweb="tab-list"] { background-color:#0a0a0a; }
.up { color:#5fd75f; }
.down { color:#ff5c5c; }
.src-note { color:#6b6b6b; font-size:11px; margin-top:8px; }
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────
# 데이터 조회 함수들 (캐시로 API 호출 최소화)
# ─────────────────────────────────────────────

@st.cache_data(ttl=60)
def get_us_indices():
    """미국 주요 지수 (yfinance)"""
    import yfinance as yf
    tickers = {"^GSPC": "S&P 500", "^IXIC": "Nasdaq", "^DJI": "Dow Jones"}
    rows = []
    for tk, name in tickers.items():
        try:
            t = yf.Ticker(tk)
            h = t.history(period="2d")
            last = h["Close"].iloc[-1]
            prev = h["Close"].iloc[-2]
            chg = (last - prev) / prev * 100
            rows.append({"지수": name, "현재가": round(last, 2), "등락률(%)": round(chg, 2)})
        except Exception as e:
            rows.append({"지수": name, "현재가": None, "등락률(%)": None})
    return pd.DataFrame(rows)


@st.cache_data(ttl=60)
def get_kr_indices():
    """국내 주요 지수 (yfinance)"""
    import yfinance as yf
    tickers = {"^KS11": "KOSPI", "^KQ11": "KOSDAQ"}
    rows = []
    for tk, name in tickers.items():
        try:
            t = yf.Ticker(tk)
            h = t.history(period="5d")
            last = h["Close"].iloc[-1]
            prev = h["Close"].iloc[-2]
            chg = (last - prev) / prev * 100
            rows.append({"지수": name, "현재가": round(last, 2), "등락률(%)": round(chg, 2)})
        except Exception:
            rows.append({"지수": name, "현재가": None, "등락률(%)": None})
    return pd.DataFrame(rows)


@st.cache_data(ttl=300)
def get_fx():
    """환율 (frankfurter.app - 무료, 키 불필요, ECB 기준)"""
    try:
        r = requests.get("https://api.frankfurter.app/latest",
                          params={"from": "USD", "to": "KRW,JPY,EUR,GBP,CNY"}, timeout=5)
        data = r.json()["rates"]
        rows = [{"통화쌍": f"USD/{k}", "환율": v} for k, v in data.items()]
        return pd.DataFrame(rows)
    except Exception as e:
        return pd.DataFrame([{"통화쌍": "조회 실패", "환율": str(e)}])


@st.cache_data(ttl=300)
def get_rss_news(feed_url, limit=10):
    """RSS 기반 뉴스 헤드라인"""
    try:
        feed = feedparser.parse(feed_url)
        items = []
        for e in feed.entries[:limit]:
            items.append({
                "제목": e.get("title", ""),
                "링크": e.get("link", ""),
                "시간": e.get("published", "")[:16]
            })
        return items
    except Exception as e:
        return [{"제목": f"조회 실패: {e}", "링크": "", "시간": ""}]


@st.cache_data(ttl=60)
def search_stock(query):
    """종목 검색 (해외: yfinance / 국내: FinanceDataReader)"""
    import yfinance as yf
    try:
        t = yf.Ticker(query)
        info = t.info
        hist = t.history(period="1mo")
        return {
            "name": info.get("longName", query),
            "sector": info.get("sector", "-"),
            "price": info.get("currentPrice", info.get("regularMarketPrice")),
            "mktcap": info.get("marketCap"),
            "summary": info.get("longBusinessSummary", "")[:400],
            "hist": hist
        }
    except Exception as e:
        return {"error": str(e)}


# ─────────────────────────────────────────────
# 화면(중분류)별 렌더 함수
# ─────────────────────────────────────────────

def page_news_domestic():
    st.subheader("국내 뉴스 (연합뉴스 경제)")
    items = get_rss_news("https://www.yna.co.kr/rss/economy.xml")
    for n in items:
        st.markdown(f"- [{n['제목']}]({n['링크']})  \n  <span class='src-note'>{n['시간']}</span>", unsafe_allow_html=True)


def page_news_global():
    st.subheader("해외 뉴스 (Reuters Business)")
    items = get_rss_news("https://feeds.reuters.com/reuters/businessNews")
    for n in items:
        st.markdown(f"- [{n['제목']}]({n['링크']})  \n  <span class='src-note'>{n['시간']}</span>", unsafe_allow_html=True)


def page_index_kr():
    st.subheader("국내 지수")
    df = get_kr_indices()
    st.dataframe(df, use_container_width=True, hide_index=True)
    st.caption(f"업데이트: {datetime.now().strftime('%H:%M:%S')} · 출처: FinanceDataReader")


def page_index_us():
    st.subheader("해외 지수")
    df = get_us_indices()
    st.dataframe(df, use_container_width=True, hide_index=True)
    st.caption(f"업데이트: {datetime.now().strftime('%H:%M:%S')} · 출처: Yahoo Finance(yfinance)")


def page_fx():
    st.subheader("환율")
    df = get_fx()
    st.dataframe(df, use_container_width=True, hide_index=True)
    st.caption(f"업데이트: {datetime.now().strftime('%H:%M:%S')} · 출처: frankfurter.app (ECB 기준)")


def page_stock_search():
    st.subheader("개별 종목 조회")
    q = st.text_input("티커 입력 (예: AAPL, TSLA, 005930.KS)", "")
    if q:
        d = search_stock(q)
        if "error" in d:
            st.error(f"조회 실패: {d['error']}")
        else:
            c1, c2 = st.columns([1, 2])
            with c1:
                st.metric(d["name"], d.get("price", "-"))
                st.write(f"섹터: {d['sector']}")
                mktcap = d.get("mktcap")
                st.write(f"시가총액: {mktcap:,}" if mktcap else "시가총액: -")
            with c2:
                if d.get("hist") is not None and not d["hist"].empty:
                    st.line_chart(d["hist"]["Close"])
            st.write(d.get("summary", ""))
    st.caption("출처: Yahoo Finance(yfinance) · 국내 종목은 '005930.KS' 형식 (.KS=코스피, .KQ=코스닥)")


def page_policy_us():
    st.subheader("미국 정책/일정 (수동 업데이트 중 — 추후 자동화 예정)")
    st.info("FOMC 등 일정은 현재 수동 목록입니다. 다음 단계에서 Fed 공식 캘린더 연동으로 자동화 가능합니다.")
    sample = pd.DataFrame([
        {"일정": "FOMC 회의", "날짜": "다음 회의 일정 확인 필요", "비고": "federalreserve.gov 캘린더 참고"},
    ])
    st.dataframe(sample, use_container_width=True, hide_index=True)
    st.markdown("[Fed 공식 캘린더](https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm)")


def page_policy_kr():
    st.subheader("한국 정책/일정 (수동 업데이트 중 — 추후 자동화 예정)")
    st.info("금통위 등 일정은 현재 수동 목록입니다. 다음 단계에서 한국은행 공식 캘린더 연동으로 자동화 가능합니다.")
    st.markdown("[한국은행 금통위 일정](https://www.bok.or.kr/portal/singl/crncyPolicyDrcMtg/listYear.do?mtgSeCd=01&menuNo=200755)")


# ─────────────────────────────────────────────
# 메뉴 구조 (대분류 → 중분류 → 렌더 함수)
# 여기에 항목만 추가하면 메뉴가 늘어남
# ─────────────────────────────────────────────
MENU = {
    "📰 뉴스브리핑": {
        "국내 뉴스": page_news_domestic,
        "해외 뉴스": page_news_global,
    },
    "📈 실시간 시황": {
        "국내 지수": page_index_kr,
        "해외 지수": page_index_us,
        "환율": page_fx,
        "종목 조회": page_stock_search,
    },
    "🏛️ 정책/일정": {
        "미국": page_policy_us,
        "한국": page_policy_kr,
    },
}

# ─────────────────────────────────────────────
# 사이드바 렌더 + 라우팅
# ─────────────────────────────────────────────
st.sidebar.title("📊 TERMINAL")
major = st.sidebar.radio("대분류", list(MENU.keys()))
minor = st.sidebar.radio("중분류", list(MENU[major].keys()))

st.title(f"{major} · {minor}")
MENU[major][minor]()
