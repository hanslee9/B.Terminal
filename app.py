"""
투자 정보 터미널 (Streamlit)
- 좌측 대분류를 폴더처럼 펼치면 하위 항목이 나오는 트리 구조
- 무료 API/공개 RSS/문서형 기관 자료만 사용
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


def render_link_table(rows):
    """rows: list of (label, url, note) — 클릭 가능한 표 형태로 렌더링"""
    html = "<table style='width:100%;border-collapse:collapse;font-size:13px;margin-bottom:10px;'>"
    for label, url, note in rows:
        html += (
            "<tr style='border-bottom:1px solid #eee;'>"
            f"<td style='padding:6px 8px;'><a href='{url}' target='_blank' style='color:#1a1a1a;text-decoration:none;font-weight:600;'>{label}</a></td>"
            f"<td style='padding:6px 8px;color:#888;font-size:11.5px;text-align:right;white-space:nowrap;'>{note}</td>"
            "</tr>"
        )
    html += "</table>"
    st.markdown(html, unsafe_allow_html=True)


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


@st.cache_data(ttl=600)
def get_naver_research(list_path, limit=15):
    """
    네이버금융 '리서치' 코너 (증권사 애널리스트 리포트 모음) 스크래핑.
    list_path 예: market_info_list.naver, industry_list.naver,
                  company_list.naver, invest_list.naver
    ※ 네이버가 페이지 구조를 바꾸면 파싱이 깨질 수 있습니다 —
      항목이 비어 나오면 알려주시면 선택자를 갱신하겠습니다.
    """
    from bs4 import BeautifulSoup
    url = f"https://finance.naver.com/research/{list_path}"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    try:
        r = requests.get(url, headers=headers, timeout=6)
        r.encoding = "euc-kr"
        soup = BeautifulSoup(r.text, "html.parser")
        rows = soup.select("table.type_1 tr")
        items = []
        for tr in rows:
            tds = tr.find_all("td")
            if len(tds) < 4:
                continue
            title_a = tds[0].find("a")
            if not title_a:
                continue
            title = title_a.get_text(strip=True)
            link = "https://finance.naver.com/research/" + title_a.get("href", "")
            broker = tds[1].get_text(strip=True)
            date = tds[-1].get_text(strip=True)
            if title:
                items.append({"제목": title, "링크": link, "증권사": broker, "날짜": date})
            if len(items) >= limit:
                break
        return items
    except Exception as e:
        return [{"제목": f"조회 실패: {e}", "링크": "", "증권사": "", "날짜": ""}]


def get_anthropic_client():
    """공용 Anthropic 클라이언트. 키 없으면 None 반환."""
    api_key = st.secrets.get("ANTHROPIC_API_KEY", None)
    if not api_key:
        return None
    import anthropic
    return anthropic.Anthropic(api_key=api_key)


def ask_ai(user_prompt, system_prompt=None, want_json=False, use_web_search=True, max_tokens=1200):
    """공용 AI 호출 헬퍼. (결과, 에러) 튜플 반환. 결과가 None이면 에러 메시지 확인."""
    client = get_anthropic_client()
    if client is None:
        return None, "API 키 없음"
    try:
        kwargs = dict(
            model="claude-sonnet-4-6",
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": user_prompt}],
        )
        if system_prompt:
            kwargs["system"] = system_prompt
        if use_web_search:
            kwargs["tools"] = [{"type": "web_search_20250305", "name": "web_search"}]
        msg = client.messages.create(**kwargs)
        text = "".join([b.text for b in msg.content if b.type == "text"]).strip()
        if want_json:
            cleaned = text.replace("```json", "").replace("```", "").strip()
            start = cleaned.find("{")
            end = cleaned.rfind("}")
            if start == -1 or end == -1:
                return None, f"JSON 파싱 실패: {cleaned[:150]}"
            import json
            return json.loads(cleaned[start:end + 1]), None
        return text, None
    except Exception as e:
        return None, str(e)


@st.cache_data(ttl=1800)
def generate_ai_briefing(context_text):
    """Anthropic API로 챕터형 서술 브리핑 생성 (API 키 필요)"""
    system = (
        "당신은 투자자를 위한 시황 브리핑 애널리스트입니다. 아래 제공된 최신 헤드라인들을 참고해서, "
        "오늘 시장에 실제로 영향을 줄 만한 주요 이벤트를 2~4개 챕터로 나누어 보고서 형식으로 작성하세요. "
        "각 챕터는 '## 챕터 제목' 형식의 마크다운 소제목 + 3~5문장의 설명으로 구성합니다. "
        "예: '## 미-이란 휴전 합의 가능성' 같은 식으로, 실제 헤드라인에 근거해 구체적인 챕터 제목을 붙이세요. "
        "확인되지 않은 내용은 추측하지 말고, 헤드라인에 나온 사실 위주로 작성하세요. 한국어로 작성하세요."
    )
    prompt = f"오늘의 헤드라인 목록:\n{context_text}\n\n위 내용을 바탕으로 브리핑을 작성해줘."
    return ask_ai(prompt, system_prompt=system, want_json=False, max_tokens=1500)


@st.cache_data(ttl=3600)
def resolve_ticker_via_ai(query):
    """사람이 입력한 종목명(띄어쓰기·오타 포함)을 실제 yfinance 티커로 변환.
    반환: {"ticker": "000660.KS", "name": "SK하이닉스"} 또는 None"""
    system = (
        "당신은 증권 티커 조회 도우미입니다. 사용자가 입력한 종목명(띄어쓰기, 약칭, 오타가 있을 수 있음)에 해당하는 "
        "Yahoo Finance 티커 심볼을 찾아 오직 JSON 객체 하나로만 답하세요. 다른 텍스트, 코드펜스 금지. "
        "형식: {\"ticker\":\"000660.KS\",\"name\":\"SK하이닉스\"}. "
        "한국 종목은 .KS(코스피) 또는 .KQ(코스닥) 접미사를 반드시 붙이세요. 해당 종목을 못 찾으면 "
        "{\"ticker\":null,\"name\":null} 로 답하세요."
    )
    prompt = f"'{query}' 종목의 Yahoo Finance 티커를 찾아줘."
    data, err = ask_ai(prompt, system_prompt=system, want_json=True, max_tokens=300)
    if data and data.get("ticker"):
        return data
    return None


@st.cache_data(ttl=60)
def search_stock(query):
    """종목 검색 (yfinance)"""
    import yfinance as yf
    try:
        t = yf.Ticker(query)
        info = t.info
        hist = t.history(period="1mo")
        if not info or (info.get("regularMarketPrice") is None and info.get("currentPrice") is None):
            return {"error": "not_found"}
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
    subtitle("브리핑")

    kr_items = get_multi_rss(FEEDS_DOMESTIC, limit_per_feed=6)
    gl_items = get_multi_rss(FEEDS_GLOBAL, limit_per_feed=6)
    all_items = kr_items + gl_items
    context = "\n".join([f"- [{it['출처']}] {it['제목']}" for it in all_items])

    text, err = generate_ai_briefing(context)

    if text:
        st.markdown(text)
        st.caption(f"AI 생성 · {datetime.now().strftime('%Y-%m-%d %H:%M')} 기준 헤드라인 참고 · 참고용, 투자판단 근거로 단독 사용 금지")
    else:
        st.info(
            "AI 서술형 종합 브리핑(여러 이슈를 챕터로 묶어 새로 써주는 기능)을 쓰려면 Anthropic API 키가 필요합니다. "
            "아래 표만으로도 충분하시면 키 설정 없이 계속 이렇게 쓰시면 됩니다."
        )
        if err and err != "API 키 없음":
            st.caption(f"오류 상세: {err}")

    st.markdown("---")
    st.caption("모두 문서(텍스트/PDF) 형태로 발행하는 곳만 정리했습니다. 유튜브 등 영상 위주 채널은 제외했습니다. "
               "매일 갱신되는 목록 페이지라 클릭하면 오늘자 최신 글이 맨 위에 있습니다.")

    st.markdown("**① 증권사**")
    render_link_table([
        ("삼성증권 — 오늘의 투자정보 (매일 아침·저녁 시황)", "https://www.samsungpop.com/v2/today-invest", "대형사"),
        ("미래에셋증권 — 리서치 리포트 전체", "https://securities.miraeasset.com/bbs/board/message/list.do?categoryId=1521", "대형사"),
        ("한국투자증권 — 리서치 센터", "https://securities.koreainvestment.com/main/research/research/Search.jsp", "대형사"),
        ("키움증권 — 경제/전략 (모닝레터·일간증시전망)", "https://www.kiwoom.com/h/invest/research/VMarketSEView", "대형사"),
        ("KB증권 — 리서치본부", "https://rc.kbsec.com/main.able", "대형사"),
    ])

    st.markdown("**② 공공·정책기관**")
    render_link_table([
        ("한국은행 — 일일 금융외환시장 동향", "https://www.bok.or.kr/portal/bbs/B0000348/list.do?menuNo=201109", "매일·완전무료"),
        ("국제금융센터(KCIF) — 국제금융속보", "https://www.kcif.or.kr/annual/newsflashList", "매일 아침·일부유료"),
        ("국제금융센터(KCIF) — 이슈브리핑", "https://www.kcif.or.kr/brief/briefList", "비정기·일부유료"),
        ("자본시장연구원(KCMI) — 자본시장포커스", "https://www.kcmi.re.kr/publications", "약 2주 1회·무료"),
    ])

    st.markdown("**③ 기타 민영 (그룹 계열 경제연구소)**")
    render_link_table([
        ("하나금융연구소", "https://www.hanaif.re.kr/", "비정기·무료"),
        ("KB경영연구소", "https://www.kbfg.com/kbresearch/report/reportList.do", "비정기·무료"),
        ("LG경영연구원", "https://www.lgbr.co.kr/business/list.do", "비정기·무료"),
        ("우리금융경영연구소", "https://www.wfri.re.kr/", "비정기·무료"),
    ])

    st.markdown("---")
    st.markdown("**중소형 증권사 모닝브리프 (원문, 네이버금융 경유)**")
    st.caption("증권사 리서치센터가 매일 문장으로 작성하는 실제 시황 브리핑입니다. AI 요약이 아닌 원문입니다.")
    brief_items = get_naver_research("market_info_list.naver", limit=5)
    if brief_items and "조회 실패" not in brief_items[0]["제목"]:
        for it in brief_items:
            st.markdown(
                f"- [{it['제목']}]({it['링크']})  \n  <span class='src-note'>{it['증권사']} · {it['날짜']}</span>",
                unsafe_allow_html=True
            )
    else:
        st.caption("현재 불러온 항목이 없습니다.")


def page_news_domestic():
    subtitle("국내 최신 뉴스 (연합뉴스·매일경제·한국경제·서울경제·이데일리)")
    items = get_multi_rss(FEEDS_DOMESTIC, limit_per_feed=5)
    for n in items:
        st.markdown(f"- [{n['제목']}]({n['링크']})  \n  <span class='src-note'>{n['출처']} · {n['시간']}</span>", unsafe_allow_html=True)


def page_news_global():
    subtitle("해외 최신 뉴스 (Reuters Business)")
    items = get_multi_rss(FEEDS_GLOBAL, limit_per_feed=10)
    for n in items:
        st.markdown(f"- [{n['제목']}]({n['링크']})  \n  <span class='src-note'>{n['출처']} · {n['시간']}</span>", unsafe_allow_html=True)


def render_research_list(list_path, source_label):
    items = get_naver_research(list_path, limit=15)
    if not items:
        st.caption("현재 불러온 항목이 없습니다.")
        return
    for it in items:
        st.markdown(
            f"- [{it['제목']}]({it['링크']})  \n  <span class='src-note'>{it['증권사']} · {it['날짜']}</span>",
            unsafe_allow_html=True
        )
    st.caption(f"출처: 네이버금융 리서치 · {source_label} (증권사 애널리스트 리포트 모음)")


def page_research_general():
    subtitle("리서치 · 종합 (시황정보)")
    render_research_list("market_info_list.naver", "시황정보")


def page_research_company():
    subtitle("리서치 · 기업분석 (종목분석)")
    render_research_list("company_list.naver", "종목분석")


def page_research_industry():
    subtitle("리서치 · 산업분석")
    render_research_list("industry_list.naver", "산업분석")


def page_research_strategy():
    subtitle("리서치 · 투자전략 (투자정보)")
    render_research_list("invest_list.naver", "투자정보")


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
    q = st.text_input("종목명 또는 티커 입력 (예: SK하이닉스, AAPL, 삼성전자)", "")
    if q:
        d = search_stock(q)
        resolved_note = None

        if "error" in d:
            # 직접 조회 실패 → AI로 정확한 티커를 찾아 재시도 (띄어쓰기/약칭/오타 대응)
            with st.spinner("정확한 티커를 못 찾아서 AI로 확인 중..."):
                resolved = resolve_ticker_via_ai(q)
            if resolved:
                d2 = search_stock(resolved["ticker"])
                if "error" not in d2:
                    d = d2
                    resolved_note = f"AI가 '{q}' → **{resolved['name']} ({resolved['ticker']})** 로 자동 인식했습니다."

        if "error" in d:
            st.error(f"조회 실패: 종목을 찾지 못했습니다. (마지막 시도값: {q})")
            if get_anthropic_client() is None:
                st.caption("AI 자동 티커 인식을 쓰려면 Anthropic API 키가 필요합니다 (브리핑 메뉴 안내 참고).")
        else:
            if resolved_note:
                st.success(resolved_note)
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
    st.caption("출처: Yahoo Finance(yfinance) · 정확한 티커를 모르면 그냥 종목명을 입력하세요 (AI가 자동 인식)")


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


def page_ai_chat():
    subtitle("AI 대화")

    if get_anthropic_client() is None:
        st.warning(
            "AI 대화를 쓰려면 Anthropic API 키가 필요합니다. "
            "Streamlit Cloud → Manage app → Settings → Secrets 에 추가해주세요:\n\n"
            "`ANTHROPIC_API_KEY = \"sk-ant-...\"`"
        )
        st.caption("예시 질문: 'SK하이닉스 티커가 뭐야?', '오늘 미국 국채금리 왜 올랐어?', '반도체 업황 전망 알려줘'")
        return

    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []

    for role, msg in st.session_state.chat_history:
        with st.chat_message(role):
            st.markdown(msg)

    q = st.chat_input("무엇이든 물어보세요 (예: SK하이닉스 티커가 뭐야?)")
    if q:
        st.session_state.chat_history.append(("user", q))
        with st.chat_message("user"):
            st.markdown(q)
        with st.chat_message("assistant"):
            with st.spinner("답변 작성 중..."):
                system = (
                    "당신은 이 투자정보 터미널 앱의 AI 비서입니다. 필요시 웹검색을 사용해 최신 정보로 "
                    "간결하고 정확하게 한국어로 답하세요. 종목명을 물으면 정확한 티커(Yahoo Finance 기준, "
                    "한국 종목은 .KS/.KQ 접미사)도 함께 알려주세요. 투자 조언이 아닌 정보 제공 목적임을 "
                    "인지하고, 확정적인 매수/매도 추천은 하지 마세요."
                )
                answer, err = ask_ai(q, system_prompt=system, max_tokens=1000)
                if answer:
                    st.markdown(answer)
                    st.session_state.chat_history.append(("assistant", answer))
                else:
                    st.error(f"오류: {err}")

    if st.session_state.chat_history:
        if st.button("대화 초기화"):
            st.session_state.chat_history = []
            st.rerun()


# ─────────────────────────────────────────────
# 메뉴 구조 (대분류 → 중분류 → 렌더 함수)
# 여기에 항목만 추가하면 메뉴가 늘어남
# ─────────────────────────────────────────────
MENU = {
    "🗞️ 브리핑": {
        "브리핑": page_briefing,
    },
    "📡 최신 뉴스": {
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
    "🤖 AI 대화": {
        "AI 대화": page_ai_chat,
    },
}

# ─────────────────────────────────────────────
# 사이드바 렌더 + 라우팅 (대분류를 폴더처럼 펼쳐서 하위 항목 클릭)
# ─────────────────────────────────────────────
st.sidebar.title("📊 TERMINAL")

if "page" not in st.session_state:
    st.session_state.page = ("🗞️ 브리핑", "브리핑")

for major, minors in MENU.items():
    is_current_group = st.session_state.page[0] == major
    with st.sidebar.expander(major, expanded=is_current_group):
        for minor in minors:
            is_active = (major, minor) == st.session_state.page
            label = f"● {minor}" if is_active else minor
            if st.button(label, key=f"nav-{major}-{minor}", use_container_width=True):
                st.session_state.page = (major, minor)
                st.rerun()

major, minor = st.session_state.page
st.markdown(f"<div class='page-title'>{major} · {minor}</div>", unsafe_allow_html=True)
MENU[major][minor]()
