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
.stApp { background-color:#ffffff; color:#1a1a1a; }
section[data-testid="stSidebar"] { background-color:#f7f7f7; border-right:1px solid #e0e0e0; }
h1,h2,h3 { color:#c05a00 !important; }
.up { color:#1a7a1a; }
.down { color:#c22; }
.src-note { color:#888; font-size:11px; margin-top:8px; }
.page-title { font-size:20px; font-weight:700; color:#c05a00; margin-bottom:4px; }
</style>
""", unsafe_allow_html=True)


def subtitle(text):
    st.markdown(f"<div style='font-size:15px;font-weight:700;color:#1a1a1a;margin:6px 0;'>{text}</div>", unsafe_allow_html=True)


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
                "시간": e.get("published", "")[:16],
                "출처": ""
            })
        return items
    except Exception as e:
        return [{"제목": f"조회 실패: {e}", "링크": "", "시간": "", "출처": ""}]


# 국내 종합경제지 RSS (다수 소스). 개별 언론사가 URL을 바꾸면 해당 피드만 빈 목록이
# 나올 수 있어, 그 경우 알려주시면 주소를 갱신하겠습니다.
FEEDS_DOMESTIC = {
    "연합뉴스": "https://www.yna.co.kr/rss/economy.xml",
    "매일경제": "https://www.mk.co.kr/rss/30000001/",
    "한국경제": "https://www.hankyung.com/feed/economy",
    "서울경제": "https://www.sedaily.com/RSS/S1N1.xml",
    "이데일리": "http://rss.edaily.co.kr/edaily_news.xml",
}
FEEDS_GLOBAL = {
    "Reuters": "https://feeds.reuters.com/reuters/businessNews",
}


@st.cache_data(ttl=300)
def get_multi_rss(feeds: dict, limit_per_feed=5):
    """여러 RSS를 합쳐 출처 태그를 붙여 반환"""
    all_items = []
    for src, url in feeds.items():
        try:
            feed = feedparser.parse(url)
            for e in feed.entries[:limit_per_feed]:
                all_items.append({
                    "제목": e.get("title", ""),
                    "링크": e.get("link", ""),
                    "시간": e.get("published", "")[:16],
                    "출처": src
                })
        except Exception:
            continue
    return all_items


def filter_by_keywords(items, keywords):
    """제목에 키워드가 하나라도 포함된 항목만 필터"""
    if not keywords:
        return items
    return [it for it in items if any(kw in it["제목"] for kw in keywords)]


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

def page_briefing():
    subtitle("오늘의 브리핑 (핵심 이슈 종합)")
    st.caption("※ 현재는 AI 서술형 요약이 아니라, 여러 소스 헤드라인 중 핵심으로 보이는 항목을 규칙 기반으로 골라 정리한 버전입니다. "
               "AI가 문장으로 써주는 진짜 '보고서형' 브리핑은 별도 API 키 연동 후 업그레이드 예정입니다.")

    kr_items = get_multi_rss(FEEDS_DOMESTIC, limit_per_feed=6)
    gl_items = get_multi_rss(FEEDS_GLOBAL, limit_per_feed=6)

    important_kw = ["코스피", "코스닥", "금리", "환율", "연준", "Fed", "실적", "무역", "관세",
                     "반도체", "수출", "인플레이션", "CPI", "FOMC", "달러", "국고채"]

    kr_pick = filter_by_keywords(kr_items, important_kw)[:6]
    gl_pick = filter_by_keywords(gl_items, important_kw)[:4]

    st.markdown("**국내 시장 핵심 이슈**")
    if kr_pick:
        for n in kr_pick:
            st.markdown(f"- [{n['제목']}]({n['링크']}) <span class='src-note'>· {n['출처']}</span>", unsafe_allow_html=True)
    else:
        st.caption("조건에 맞는 핵심 이슈를 찾지 못했습니다.")

    st.markdown("**해외 시장 핵심 이슈**")
    if gl_pick:
        for n in gl_pick:
            st.markdown(f"- [{n['제목']}]({n['링크']}) <span class='src-note'>· {n['출처']}</span>", unsafe_allow_html=True)
    else:
        st.caption("조건에 맞는 핵심 이슈를 찾지 못했습니다.")


def page_news_domestic():
    subtitle("국내 뉴스 (연합뉴스·매일경제·한국경제·서울경제·이데일리)")
    items = get_multi_rss(FEEDS_DOMESTIC, limit_per_feed=5)
    for n in items:
        st.markdown(f"- [{n['제목']}]({n['링크']})  \n  <span class='src-note'>{n['출처']} · {n['시간']}</span>", unsafe_allow_html=True)


def page_news_global():
    subtitle("해외 뉴스 (Reuters Business)")
    items = get_multi_rss(FEEDS_GLOBAL, limit_per_feed=10)
    for n in items:
        st.markdown(f"- [{n['제목']}]({n['링크']})  \n  <span class='src-note'>{n['출처']} · {n['시간']}</span>", unsafe_allow_html=True)


def page_research_general():
    subtitle("리서치 · 종합")
    items = get_multi_rss(FEEDS_DOMESTIC, limit_per_feed=6)
    for n in items[:12]:
        st.markdown(f"- [{n['제목']}]({n['링크']}) <span class='src-note'>· {n['출처']}</span>", unsafe_allow_html=True)
    st.caption("※ 임시로 종합경제지 헤드라인을 그대로 노출 중입니다. 증권사 리서치센터 리포트 연동은 다음 단계 협의 후 진행합니다.")


def page_research_company():
    subtitle("리서치 · 기업분석")
    items = filter_by_keywords(get_multi_rss(FEEDS_DOMESTIC, limit_per_feed=8),
                                ["실적", "목표주가", "영업이익", "순이익", "리포트", "매수", "매도"])
    if items:
        for n in items[:12]:
            st.markdown(f"- [{n['제목']}]({n['링크']}) <span class='src-note'>· {n['출처']}</span>", unsafe_allow_html=True)
    else:
        st.caption("현재 조건에 맞는 기사가 없습니다.")
    st.caption("※ 키워드 기반 임시 필터입니다.")


def page_research_industry():
    subtitle("리서치 · 산업분석")
    items = filter_by_keywords(get_multi_rss(FEEDS_DOMESTIC, limit_per_feed=8),
                                ["업황", "산업", "공급망", "규제", "수주", "생산"])
    if items:
        for n in items[:12]:
            st.markdown(f"- [{n['제목']}]({n['링크']}) <span class='src-note'>· {n['출처']}</span>", unsafe_allow_html=True)
    else:
        st.caption("현재 조건에 맞는 기사가 없습니다.")
    st.caption("※ 키워드 기반 임시 필터입니다.")


def page_research_strategy():
    subtitle("리서치 · 투자전략")
    items = filter_by_keywords(get_multi_rss(FEEDS_DOMESTIC, limit_per_feed=8),
                                ["증시", "전망", "금리", "환율", "투자전략", "포트폴리오", "자산배분"])
    if items:
        for n in items[:12]:
            st.markdown(f"- [{n['제목']}]({n['링크']}) <span class='src-note'>· {n['출처']}</span>", unsafe_allow_html=True)
    else:
        st.caption("현재 조건에 맞는 기사가 없습니다.")
    st.caption("※ 키워드 기반 임시 필터입니다.")


def page_index_kr():
    subtitle("국내 지수")
    df = get_kr_indices()
    st.dataframe(df, use_container_width=True, hide_index=True)
    st.caption(f"업데이트: {datetime.now().strftime('%H:%M:%S')} · 출처: FinanceDataReader")


def page_index_us():
    subtitle("해외 지수")
    df = get_us_indices()
    st.dataframe(df, use_container_width=True, hide_index=True)
    st.caption(f"업데이트: {datetime.now().strftime('%H:%M:%S')} · 출처: Yahoo Finance(yfinance)")


def page_fx():
    subtitle("환율")
    df = get_fx()
    st.dataframe(df, use_container_width=True, hide_index=True)
    st.caption(f"업데이트: {datetime.now().strftime('%H:%M:%S')} · 출처: frankfurter.app (ECB 기준)")


def page_stock_search():
    subtitle("개별 종목 조회")
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
    subtitle("미국 정책/일정 (수동 업데이트 중 — 추후 자동화 예정)")
    st.info("FOMC 등 일정은 현재 수동 목록입니다. 다음 단계에서 Fed 공식 캘린더 연동으로 자동화 가능합니다.")
    sample = pd.DataFrame([
        {"일정": "FOMC 회의", "날짜": "다음 회의 일정 확인 필요", "비고": "federalreserve.gov 캘린더 참고"},
    ])
    st.dataframe(sample, use_container_width=True, hide_index=True)
    st.markdown("[Fed 공식 캘린더](https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm)")


def page_policy_kr():
    subtitle("한국 정책/일정 (수동 업데이트 중 — 추후 자동화 예정)")
    st.info("금통위 등 일정은 현재 수동 목록입니다. 다음 단계에서 한국은행 공식 캘린더 연동으로 자동화 가능합니다.")
    st.markdown("[한국은행 금통위 일정](https://www.bok.or.kr/portal/singl/crncyPolicyDrcMtg/listYear.do?mtgSeCd=01&menuNo=200755)")


# ─────────────────────────────────────────────
# 메뉴 구조 (대분류 → 중분류 → 렌더 함수)
# 여기에 항목만 추가하면 메뉴가 늘어남
# ─────────────────────────────────────────────
MENU = {
    "🗞️ 뉴스브리핑": {
        "오늘의 브리핑": page_briefing,
    },
    "📡 뉴스": {
        "국내 뉴스": page_news_domestic,
        "해외 뉴스": page_news_global,
    },
    "🔎 리서치": {
        "종합": page_research_general,
        "기업분석": page_research_company,
        "산업분석": page_research_industry,
        "투자전략": page_research_strategy,
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

st.markdown(f"<div class='page-title'>{major} · {minor}</div>", unsafe_allow_html=True)
MENU[major][minor]()
