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
.app-title { font-size:26px; font-weight:800; color:#1a1a1a; margin-bottom:2px; }
</style>
""", unsafe_allow_html=True)


def check_password():
    """
    st.secrets에 APP_PASSWORD가 설정되어 있으면 비밀번호 입력 전까지 앱 진입을 막습니다.
    설정 안 되어 있으면 게이트 없이 그대로 통과 (기존처럼 동작).
    """
    app_password = st.secrets.get("APP_PASSWORD", None)
    if not app_password:
        return  # 비밀번호 미설정 → 제한 없음

    if st.session_state.get("authenticated", False):
        return

    st.markdown("<div style='font-weight:700;font-size:18px;color:#c05a00;margin-top:60px;'>🔒 접근 제한</div>", unsafe_allow_html=True)
    pwd = st.text_input("비밀번호를 입력하세요", type="password", key="pwd_input")
    if st.button("확인"):
        if pwd == app_password:
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error("비밀번호가 틀렸습니다.")
    st.stop()


check_password()


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


def render_category_lists(categories: dict):
    """categories: {카테고리명: [(기관명, url), ...]} — 표 대신 구분선 없는 섹션별 리스트.
    항목 추가/삭제가 쉽도록 각 카테고리 아래 단순 나열."""
    cols = st.columns(len(categories))
    for col, (cat_name, items) in zip(cols, categories.items()):
        with col:
            st.markdown(f"<div style='font-weight:700;font-size:13px;color:#c05a00;margin-bottom:6px;'>{cat_name}</div>", unsafe_allow_html=True)
            if not items:
                st.markdown("<div style='color:#bbb;font-size:12px;'>(추가 예정)</div>", unsafe_allow_html=True)
            for name, url in items:
                st.markdown(
                    f"<div style='padding:3px 0;font-size:12.5px;'>"
                    f"<a href='{url}' target='_blank' style='color:#1155cc;text-decoration:none;'>{name}</a>"
                    f"</div>",
                    unsafe_allow_html=True
                )


# ─────────────────────────────────────────────
# 데이터 조회 함수들 (캐시로 API 호출 최소화)
# ─────────────────────────────────────────────

@st.cache_data(ttl=60)
def get_us_indices():
    """해외 주요 지수 (yfinance) — 국내지수와 동일한 컬럼 템플릿"""
    import yfinance as yf
    tickers = {
        "^GSPC": ("S&P 500", "미국"),
        "^IXIC": ("Nasdaq", "미국"),
        "^DJI": ("Dow Jones", "미국"),
        "^N225": ("Nikkei 225", "일본"),
        "^FTSE": ("FTSE 100", "영국"),
        "^GDAXI": ("DAX", "독일"),
        "^FCHI": ("CAC 40", "프랑스"),
    }
    rows = []
    for tk, (name, country) in tickers.items():
        try:
            t = yf.Ticker(tk)
            h = t.history(period="10d").dropna(subset=["Close"])  # 휴장일 빈 행 제외
            last_row = h.iloc[-1]
            prev_close = h["Close"].iloc[-2]
            chg = (last_row["Close"] - prev_close) / prev_close * 100
            h1y = t.history(period="1y").dropna(subset=["Close"])
            high52 = h1y["High"].max() if not h1y.empty else None
            low52 = h1y["Low"].min() if not h1y.empty else None
            rows.append({
                "지수": name,
                "국가": country,
                "현재가": round(last_row["Close"], 2),
                "전일대비": round(last_row["Close"] - prev_close, 2),
                "등락률(%)": round(chg, 2),
                "거래량": int(last_row["Volume"]) if last_row["Volume"] else None,
                "52주 최고": round(high52, 2) if high52 is not None else None,
                "52주 최저": round(low52, 2) if low52 is not None else None,
            })
        except Exception:
            rows.append({"지수": name, "국가": country, "현재가": None, "전일대비": None,
                          "등락률(%)": None, "거래량": None, "52주 최고": None, "52주 최저": None})
    return pd.DataFrame(rows)


@st.cache_data(ttl=120)
def get_us_sector_performance():
    """
    미국 섹터별 등락률 — SPDR Select Sector ETF 11종 (yfinance, 스크래핑 없이 안정적)
    S&P 500을 11개 GICS 섹터로 나눈 대표 ETF들의 당일 등락률로 섹터 동향을 근사.
    """
    import yfinance as yf
    sector_etfs = {
        "XLK": "기술(Technology)",
        "XLF": "금융(Financials)",
        "XLE": "에너지(Energy)",
        "XLV": "헬스케어(Health Care)",
        "XLI": "산업재(Industrials)",
        "XLY": "임의소비재(Cons. Discretionary)",
        "XLP": "필수소비재(Cons. Staples)",
        "XLU": "유틸리티(Utilities)",
        "XLB": "소재(Materials)",
        "XLRE": "부동산(Real Estate)",
        "XLC": "커뮤니케이션(Communication)",
    }
    rows = []
    for tk, name in sector_etfs.items():
        try:
            t = yf.Ticker(tk)
            h = t.history(period="5d").dropna(subset=["Close"])
            last = h["Close"].iloc[-1]
            prev = h["Close"].iloc[-2]
            chg = (last - prev) / prev * 100
            rows.append({"섹터": name, "ETF": tk, "등락률(%)": round(chg, 2)})
        except Exception:
            rows.append({"섹터": name, "ETF": tk, "등락률(%)": None})
    return rows


@st.cache_data(ttl=60)
def get_kr_indices():
    """국내 주요 지수 (yfinance) — 거래량/52주 최고·최저 포함"""
    import yfinance as yf
    tickers = {"^KS11": "KOSPI", "^KQ11": "KOSDAQ"}
    rows = []
    for tk, name in tickers.items():
        try:
            t = yf.Ticker(tk)
            h = t.history(period="10d").dropna(subset=["Close"])  # 휴장일 빈 행 제외
            last_row = h.iloc[-1]
            prev_close = h["Close"].iloc[-2]
            chg = (last_row["Close"] - prev_close) / prev_close * 100
            h1y = t.history(period="1y").dropna(subset=["Close"])
            high52 = h1y["High"].max() if not h1y.empty else None
            low52 = h1y["Low"].min() if not h1y.empty else None
            rows.append({
                "지수": name,
                "현재가": round(last_row["Close"], 2),
                "전일대비": round(last_row["Close"] - prev_close, 2),
                "등락률(%)": round(chg, 2),
                "거래량": int(last_row["Volume"]) if last_row["Volume"] else None,
                "52주 최고": round(high52, 2) if high52 is not None else None,
                "52주 최저": round(low52, 2) if low52 is not None else None,
            })
        except Exception:
            rows.append({"지수": name, "현재가": None, "전일대비": None, "등락률(%)": None,
                          "거래량": None, "52주 최고": None, "52주 최저": None})
    return pd.DataFrame(rows)


@st.cache_data(ttl=120)
def get_naver_market_breadth(index_code):
    """
    상승/보합/하락 종목수. index_code: 'KOSPI' 또는 'KOSDAQ'
    페이지 전체 텍스트에서 '상승/보합/하락' 뒤에 오는 숫자를 정규식으로 찾는 방식 —
    세부 HTML 구조 변경에 비교적 덜 민감하지만 100% 정확 보장은 아닙니다.
    """
    import re
    url = f"https://finance.naver.com/sise/sise_index.naver?code={index_code}"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    try:
        r = requests.get(url, headers=headers, timeout=6)
        r.encoding = "euc-kr"
        text = r.text
        up = re.search(r"상승[^\d]{0,15}([\d,]+)", text)
        flat = re.search(r"보합[^\d]{0,15}([\d,]+)", text)
        down = re.search(r"하락[^\d]{0,15}([\d,]+)", text)
        if up and down:
            return {
                "상승": int(up.group(1).replace(",", "")),
                "보합": int(flat.group(1).replace(",", "")) if flat else None,
                "하락": int(down.group(1).replace(",", "")),
            }
        return None
    except Exception:
        return None


@st.cache_data(ttl=300)
def fmt_num(n, unit=""):
    """천단위 콤마 + 음수는 빨간색 HTML로 포맷"""
    if n is None:
        return "-"
    color = "#c22" if n < 0 else "#1a1a1a"
    sign = "+" if n > 0 else ""
    return f"<span style='color:{color};'>{sign}{n:,.0f}{unit}</span>"


@st.cache_data(ttl=300)
def get_naver_investor_trend(sosok):
    """
    투자자별(외국인/기관/개인) 순매수 동향 (억원) — 당일/주간누계/월간누계.
    sosok: '0'=코스피, '1'=코스닥
    ※ data.krx.co.kr는 2024-12부터 로그인 없이는 차단되어(전업계 공통 이슈),
      대신 stock.naver.com의 비공식 공개 API(로그인/쿠키 불필요)를 사용합니다.
      investorGubun 코드는 실제 응답으로 검증 완료:
        8000=개인, 9000+9001=외국인(+기타외국인), 나머지(1000~7100)=기관
        (하루 합계가 0에 수렴하는 것으로 매핑 정확성 확인됨)
    """
    market_type = "KOSPI" if str(sosok) == "0" else "KOSDAQ"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                       "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://stock.naver.com/",
    }
    try:
        today = datetime.now()
        bizdate = today.strftime("%Y%m%d")
        url = "https://stock.naver.com/api/domestic/market/trend/daily"
        params = {
            "tradeType": "KRX",
            "marketType": market_type,
            "bizdate": bizdate,
            "startIdx": 0,
            "pageSize": 20,
        }
        r = requests.get(url, headers=headers, params=params, timeout=8)
        data = r.json()
        content = data.get("content", [])
        if not content:
            return None

        def parse_int(v):
            try:
                return int(str(v).replace(",", ""))
            except (ValueError, TypeError):
                return 0

        rows = []
        for day in content:
            date_raw = str(day.get("bizdate", ""))
            if not date_raw or len(date_raw) != 8:
                continue
            date_txt = f"{date_raw[:4]}-{date_raw[4:6]}-{date_raw[6:]}"

            individual = foreigner = institution = 0
            for na in day.get("netAmounts", []):
                code = str(na.get("investorGubun", ""))
                val = parse_int(na.get("diffValue", 0))
                if code == "8000":
                    individual += val
                elif code in ("9000", "9001"):
                    foreigner += val
                else:
                    institution += val

            rows.append({
                "날짜": date_txt,
                "개인": individual // 100_000_000,
                "외국인": foreigner // 100_000_000,
                "기관": institution // 100_000_000,
            })

        if not rows:
            return None

        rows.sort(key=lambda x: x["날짜"], reverse=True)  # 최신 날짜 먼저
        latest = rows[0]
        week_rows = rows[:5]
        month_rows = rows[:20]

        def sum_col(rs, col):
            return sum(r[col] for r in rs)

        return {
            "당일": latest,
            "주간누계": {c: sum_col(week_rows, c) for c in ("개인", "외국인", "기관")},
            "월간누계": {c: sum_col(month_rows, c) for c in ("개인", "외국인", "기관")},
        }
    except Exception:
        return None


@st.cache_data(ttl=300)
def get_naver_sector_list():
    """
    업종별(섹터) 전체 목록 — 등락률 + 전체종목수/상승/보합/하락.
    실제 확인된 컬럼 구조: [업종명, 등락률(%), 전체종목수, 상승, 보합, 하락, 등락그래프(%)]
    limit 없이 전체(약 80개)를 반환. 화면에서 필요한 만큼 잘라 쓰면 됨.
    """
    from bs4 import BeautifulSoup
    url = "https://finance.naver.com/sise/sise_group.naver?type=upjong"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    try:
        r = requests.get(url, headers=headers, timeout=6)
        r.encoding = "euc-kr"
        soup = BeautifulSoup(r.text, "html.parser")
        table = soup.select_one("table.type_1")
        if not table:
            return []

        rows = []
        for tr in table.select("tr"):
            name_a = tr.find("a")
            if not name_a:
                continue
            name = name_a.get_text(strip=True)
            tds = tr.find_all("td")
            cell_texts = [td.get_text(strip=True) for td in tds]
            if len(cell_texts) < 6:
                continue

            chg_str = cell_texts[1]
            try:
                chg_val = float(chg_str.replace("%", "").replace("+", ""))
            except ValueError:
                chg_val = 0.0

            rows.append({
                "업종": name,
                "등락률(%)": chg_str,
                "_등락률_값": chg_val,  # 정렬용 (화면 표시 안 함)
                "전체": cell_texts[2],
                "상승": cell_texts[3],
                "보합": cell_texts[4],
                "하락": cell_texts[5],
            })
        return rows
    except Exception:
        return []


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
    "CNBC": "https://www.cnbc.com/id/10001147/device/rss/rss.html",
    "MarketWatch": "https://feeds.content.dowjones.io/public/rss/mw_topstories",
    "Yahoo Finance": "https://finance.yahoo.com/news/rssindex",
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


# 경제/금융/투자 관련 키워드 — 국내 뉴스에서 정치·사회 기사 걸러내는 용도
ECON_KEYWORDS = [
    "코스피", "코스닥", "증시", "주가", "주식", "채권", "금리", "환율", "달러", "원화", "엔화",
    "경제", "금융", "투자", "펀드", "부동산", "물가", "인플레이션", "GDP", "실적", "매출",
    "영업이익", "순이익", "기업", "산업", "수출", "수입", "무역", "관세", "연준", "Fed", "FOMC",
    "한국은행", "예산", "세금", "증권", "IPO", "상장", "인수합병", "M&A", "반도체", "배터리",
    "원자재", "유가", "스타트업", "벤처", "암호화폐", "비트코인", "은행", "보험", "카드", "대출",
    "자산", "배당", "공모주", "상장폐지", "실업률", "고용", "소비자물가", "CPI", "무역수지",
    "경상수지", "국채", "회사채", "리츠", "ETF", "펀드매니저", "애널리스트", "리포트", "전망",
    # 대기업/총수 관련 (공장·설비투자, 총수 발언 등 간접적으로 중요한 기사 포착용)
    "팹", "공장", "생산시설", "메모리", "파운드리", "설비투자", "증설", "가동",
    "삼성전자", "SK하이닉스", "SK그룹", "현대차", "기아", "LG전자", "LG에너지솔루션",
    "롯데", "한화", "포스코", "네이버", "카카오", "쿠팡",
    "최태원", "이재용", "정의선", "구광모", "신동빈", "김승연", "최정우",
    "대미투자", "관세인상", "관세협상", "무역협상", "공급망"
]


def filter_econ_relevant(items):
    return filter_by_keywords(items, ECON_KEYWORDS)


@st.cache_data(ttl=600)
def ai_filter_econ_relevant(items_tuple):
    """AI로 경제/금융/투자 관련성을 직접 판단 (키워드보다 정확, API 키 필요).
    items_tuple: ((제목, 링크, 시간, 출처), ...) 형태 — 캐시 위해 튜플로 받음"""
    items = [{"제목": t, "링크": l, "시간": tm, "출처": s} for (t, l, tm, s) in items_tuple]
    numbered = "\n".join([f"{i}: {it['제목']}" for i, it in enumerate(items)])
    system = (
        "당신은 뉴스 분류기입니다. 아래 번호가 매겨진 기사 제목 목록에서, 경제·금융·증시·기업 실적/투자·산업 동향과 "
        "관련된 기사만 골라 번호 배열을 오직 JSON으로만 답하세요. 순수 정치/외교/사회/연예/스포츠 기사는 제외하되, "
        "기업 총수 발언, 공장·설비 투자, 무역/관세처럼 경제에 실질적 영향을 주는 기사는 포함하세요. "
        "형식: {\"keep\": [0,2,5,...]}"
    )
    data, err = ask_ai(numbered, system_prompt=system, want_json=True, use_web_search=False, max_tokens=500)
    if data and "keep" in data:
        idx = set(data["keep"])
        return [it for i, it in enumerate(items) if i in idx]
    return items  # 실패 시 원본 그대로


@st.cache_data(ttl=600)
def ai_rank_news(items_tuple):
    """AI로 시장 영향력(중요도) 순으로 재정렬. 실패 시 원본 순서 유지.
    items_tuple: ((제목, 링크, 시간, 출처), ...) 형태 — 캐시 위해 튜플로 받음"""
    items = [{"제목": t, "링크": l, "시간": tm, "출처": s} for (t, l, tm, s) in items_tuple]
    if not items:
        return items
    numbered = "\n".join([f"{i}: {it['제목']}" for i, it in enumerate(items)])
    system = (
        "당신은 시황 데스크 편집자입니다. 아래 번호가 매겨진 기사 제목 목록을, 오늘 시장·투자자에게 미치는 "
        "영향력이 큰 순서대로(가장 중요한 것부터) 재정렬하세요. 전 종목/지수 등 광범위한 영향을 주는 기사, "
        "주요 정책·금리·환율 변화, 대기업 총수 발언·대규모 투자 결정을 우선시하고, 단신·사소한 기사는 뒤로 "
        "보내세요. 모든 번호를 빠짐없이 포함해 오직 JSON으로만 답하세요. 형식: {\"ranked\": [3,0,7,...]}"
    )
    data, err = ask_ai(numbered, system_prompt=system, want_json=True, use_web_search=False, max_tokens=600)
    if data and "ranked" in data:
        order = [i for i in data["ranked"] if isinstance(i, int) and 0 <= i < len(items)]
        seen = set(order)
        order += [i for i in range(len(items)) if i not in seen]
        return [items[i] for i in order]
    return items  # 실패 시 원본 순서 그대로


def render_news_collapsible(items, key_prefix, top_n=10):
    """상위 top_n개만 바로 노출, 나머지는 접어서 표시. API 키가 있으면 AI 중요도 정렬 옵션 제공."""
    if get_anthropic_client() is not None and items:
        use_ai_rank = st.checkbox("AI로 중요도 순 정렬", value=False, key=f"{key_prefix}_ai_rank")
        if use_ai_rank:
            items_tuple = tuple((it["제목"], it["링크"], it["시간"], it["출처"]) for it in items)
            items = ai_rank_news(items_tuple)

    if not items:
        st.caption("조건에 맞는 기사가 없습니다.")
        return

    def render_item(n):
        st.markdown(f"- [{n['제목']}]({n['링크']})  \n  <span class='src-note'>{n['출처']} · {n['시간']}</span>", unsafe_allow_html=True)

    for n in items[:top_n]:
        render_item(n)

    rest = items[top_n:]
    if rest:
        with st.expander(f"그 외 {len(rest)}건 더보기"):
            for n in rest:
                render_item(n)


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
    from urllib.parse import urljoin
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
            link = urljoin(url, title_a.get("href", ""))
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
    """Anthropic API로 고정 카테고리·중요도순 브리핑 생성 (API 키 필요)"""
    system = (
        "당신은 투자자를 위한 시황 브리핑 애널리스트입니다. 아래 제공된 최신 헤드라인들을 참고해서, "
        "반드시 아래 5개 카테고리 순서 그대로, 마크다운 '## 카테고리명' 소제목으로 브리핑을 작성하세요:\n"
        "## 지수\n## 환율·금리\n## 실적·공시·특징주\n## 산업·기업 이슈\n## 기타 주요 이슈\n\n"
        "각 카테고리 안에서는 오늘 시장에 영향이 큰 순서(중요도 순)로 2~4개 항목을 글머리표(-)로 정리하고, "
        "각 항목은 1~2문장으로 간결하게 씁니다. 해당 카테고리에 관련 헤드라인이 전혀 없으면 "
        "'- 특이사항 없음'이라고만 쓰고 넘어가세요. 확인되지 않은 내용은 추측하지 말고 헤드라인에 나온 "
        "사실 위주로 작성하세요. 한국어로 작성하세요."
    )
    prompt = f"오늘의 헤드라인 목록:\n{context_text}\n\n위 내용을 바탕으로 브리핑을 작성해줘."
    return ask_ai(prompt, system_prompt=system, want_json=False, max_tokens=1500)


@st.cache_data(ttl=3600)
def resolve_ticker_free(query):
    """야후파이낸스 무료 종목검색(키 불필요)으로 티커 자동 인식.
    반환: {"ticker": "000660.KS", "name": "SK하이닉스"} 또는 None"""
    try:
        r = requests.get(
            "https://query1.finance.yahoo.com/v1/finance/search",
            params={"q": query, "quotesCount": 5, "newsCount": 0},
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=5
        )
        data = r.json()
        quotes = data.get("quotes", [])
        # 종목(EQUITY)만, 한국 종목은 .KS/.KQ 우선순위 없이 첫 매치 사용
        for q in quotes:
            if q.get("quoteType") == "EQUITY" and q.get("symbol"):
                return {"ticker": q["symbol"], "name": q.get("longname") or q.get("shortname") or query}
        return None
    except Exception:
        return None


@st.cache_data(ttl=3600)
def resolve_ticker_via_ai(query):
    """(무료 조회 실패 시 폴백) AI로 티커 인식 — API 키 필요.
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
    kr_items = get_multi_rss(FEEDS_DOMESTIC, limit_per_feed=6)
    gl_items = get_multi_rss(FEEDS_GLOBAL, limit_per_feed=6)
    all_items = kr_items + gl_items
    context = "\n".join([f"- [{it['출처']}] {it['제목']}" for it in all_items])

    text, err = generate_ai_briefing(context)

    if text:
        st.markdown(text)
        st.caption(f"AI 생성 · {datetime.now().strftime('%Y-%m-%d %H:%M')} 기준 헤드라인 참고 · 참고용, 투자판단 근거로 단독 사용 금지")
        st.markdown("---")

    st.caption("모두 문서(텍스트/PDF) 형태로 발행하는 곳만 정리했습니다. 유튜브 등 영상 위주 채널은 제외했습니다. "
               "기관명을 클릭하면 해당 페이지로 바로 이동합니다.")

    render_category_lists({
        "증권사": [
            ("삼성증권", "https://www.samsungpop.com/v2/today-invest"),
            ("미래에셋증권", "https://securities.miraeasset.com/bbs/board/message/list.do?categoryId=1521"),
            ("한국투자증권", "https://securities.koreainvestment.com/main/research/research/Search.jsp"),
            ("DS투자증권", "https://www.ds-sec.co.kr/bbs/board.php?bo_table=sub03_03"),
            ("유안타증권", "https://www.myasset.com/myasset/research/RS_0000000_M.cmd"),
        ],
        "공공 정책기관": [
            ("한국은행 - 일일 금융시장 동향", "https://www.bok.or.kr/portal/bbs/B0000348/list.do?menuNo=201109"),
            ("국제금융센터 (KCIF)", "https://www.kcif.or.kr/annual/newsflashList"),
            ("자본시장연구원 (KCMI)", "https://www.kcmi.re.kr/publications"),
        ],
        "기타, 민영 기업/연구소": [
            ("하나금융연구소", "https://www.hanaif.re.kr/"),
            ("KB경영연구소", "https://www.kbfg.com/kbresearch/report/reportList.do"),
            ("LG경영연구원", "https://www.lgbr.co.kr/business/list.do"),
            ("우리금융경영연구소", "https://www.wfri.re.kr/"),
        ],
        "포털 / 해외": [
            ("네이버 금융", "https://finance.naver.com/research/"),
            ("야후파이낸스", "https://finance.yahoo.com"),
            ("Axios Markets", "https://www.axios.com/newsletters/axios-markets"),
            ("Morning Brew", "https://www.morningbrew.com/daily"),
            ("Seeking Alpha - Wall Street Breakfast", "https://seekingalpha.com/market-news/wall-street-breakfast"),
            ("The Daily Upside", "https://www.thedailyupside.com"),
        ],
    })


def page_news_domestic():
    subtitle("국내 최신 뉴스 (연합뉴스·매일경제·한국경제·서울경제·이데일리)")

    c1, c2 = st.columns(2)
    with c1:
        only_econ = st.checkbox("경제·금융·투자 관련만 보기", value=True, key="news_domestic_filter")
    with c2:
        use_ai_filter = False
        if only_econ and get_anthropic_client() is not None:
            use_ai_filter = st.checkbox("AI로 관련성 정밀 판단", value=False, key="news_domestic_ai_filter")

    items = get_multi_rss(FEEDS_DOMESTIC, limit_per_feed=10 if only_econ else 5)

    if only_econ:
        if use_ai_filter:
            items_tuple = tuple((it["제목"], it["링크"], it["시간"], it["출처"]) for it in items)
            items = ai_filter_econ_relevant(items_tuple)
        else:
            items = filter_econ_relevant(items)

    render_news_collapsible(items, key_prefix="news_domestic", top_n=10)


def page_news_global():
    subtitle("해외 최신 뉴스 (Reuters·CNBC·MarketWatch·Yahoo Finance)")

    use_ai_filter = False
    if get_anthropic_client() is not None:
        use_ai_filter = st.checkbox("AI로 경제·금융 관련성 정밀 판단", value=False, key="news_global_ai_filter")

    items = get_multi_rss(FEEDS_GLOBAL, limit_per_feed=10)

    if use_ai_filter:
        items_tuple = tuple((it["제목"], it["링크"], it["시간"], it["출처"]) for it in items)
        items = ai_filter_econ_relevant(items_tuple)

    render_news_collapsible(items, key_prefix="news_global", top_n=10)


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


@st.cache_data(ttl=300)
def get_company_metrics(ticker):
    """yfinance에서 핵심 밸류에이션·수익성 지표 추출"""
    import yfinance as yf
    try:
        info = yf.Ticker(ticker).info
        if not info or (info.get("regularMarketPrice") is None and info.get("currentPrice") is None):
            return None
        return {
            "종목명": info.get("longName", ticker),
            "현재가": info.get("currentPrice", info.get("regularMarketPrice")),
            "시가총액": info.get("marketCap"),
            "PER": info.get("trailingPE"),
            "Forward PER": info.get("forwardPE"),
            "PBR": info.get("priceToBook"),
            "배당수익률(%)": (info.get("dividendYield") * 100) if info.get("dividendYield") else None,
            "ROE(%)": (info.get("returnOnEquity") * 100) if info.get("returnOnEquity") else None,
            "영업이익률(%)": (info.get("operatingMargins") * 100) if info.get("operatingMargins") else None,
            "매출성장률(%)": (info.get("revenueGrowth") * 100) if info.get("revenueGrowth") else None,
            "52주 최고": info.get("fiftyTwoWeekHigh"),
            "52주 최저": info.get("fiftyTwoWeekLow"),
            "섹터": info.get("sector"),
            "산업": info.get("industry"),
            "요약": info.get("longBusinessSummary", "")[:500],
        }
    except Exception:
        return None


def page_research_company():
    subtitle("리서치 · 기업분석")
    q = st.text_input("분석할 종목명 또는 티커 입력 (예: 삼성전자, AAPL)", key="research_company_query")
    if not q:
        st.caption("종목을 입력하면 핵심 지표 테이블과 AI 요약을 보여드립니다.")
        return

    d = search_stock(q)
    ticker_used = q
    if "error" in d:
        resolved = resolve_ticker_free(q)
        if resolved:
            ticker_used = resolved["ticker"]

    metrics = get_company_metrics(ticker_used)
    if not metrics:
        st.error(f"'{q}' 종목 정보를 찾지 못했습니다.")
        return

    st.markdown(f"#### {metrics['종목명']} ({ticker_used})")

    labels = ["현재가", "시가총액", "PER", "Forward PER", "PBR", "배당수익률(%)",
              "ROE(%)", "영업이익률(%)", "매출성장률(%)", "52주 최고", "52주 최저", "섹터", "산업"]
    rows = []
    for label in labels:
        val = metrics.get(label)
        if val is None:
            val_str = "-"
        elif isinstance(val, float):
            val_str = f"{val:,.2f}"
        elif isinstance(val, int):
            val_str = f"{val:,}"
        else:
            val_str = str(val)
        rows.append({"지표": label, "값": val_str})
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    if get_anthropic_client() is not None:
        system = (
            "당신은 증권 애널리스트입니다. 아래 기업 지표를 바탕으로 3~4문장으로 핵심만 서술하세요. "
            "밸류에이션 수준, 수익성, 특징을 간결하게 짚되, 매수/매도 추천은 하지 마세요. 한국어로 작성하세요."
        )
        context = "\n".join([f"{r['지표']}: {r['값']}" for r in rows]) + f"\n사업개요: {metrics.get('요약', '')}"
        summary, err = ask_ai(context, system_prompt=system, use_web_search=False, max_tokens=400)
        if summary:
            st.markdown("**AI 요약**")
            st.markdown(summary)
    else:
        st.caption("AI 서술 요약을 쓰려면 API 키가 필요합니다 (지표 테이블은 키 없이 무료로 제공됩니다).")

    st.markdown("---")
    if ticker_used.upper().endswith((".KS", ".KQ")):
        code = ticker_used.split(".")[0]
        st.markdown(
            f"[네이버금융에서 {metrics['종목명']} 관련 증권사 리포트 더 보기]"
            f"(https://finance.naver.com/research/company_list.naver?searchType=itemCode&itemCode={code})"
        )
    else:
        st.markdown(f"[Seeking Alpha에서 {ticker_used} 관련 애널리스트 리포트 더 보기](https://seekingalpha.com/symbol/{ticker_used})")


@st.cache_data(ttl=1800)
def generate_research_report(context_text):
    """리서치·종합용 — 브리핑보다 긴 서술형 정식 리포트 (API 키 필요)"""
    system = (
        "당신은 증권사 리서치센터가 발행하는 '데일리 시황 리포트'를 작성하는 애널리스트입니다. "
        "아래 헤드라인을 참고해 다음 구조로 마크다운 '## 소제목'을 사용한 정식 리포트를 쓰세요:\n"
        "## 국내 증시 동향\n## 해외 증시 동향\n## 환율·금리·원자재\n## 산업/기업 이슈\n## 투자 시사점\n\n"
        "브리핑처럼 짧은 글머리표가 아니라, 실제 증권사 리포트처럼 각 섹션을 원인-현황-전망을 갖춘 "
        "3~5문장의 완결된 문단으로 서술하세요. 확인되지 않은 내용은 추측하지 말고 헤드라인 사실 위주로 "
        "작성하세요. 한국어로 작성하세요."
    )
    prompt = f"오늘의 헤드라인 목록:\n{context_text}\n\n위 내용을 바탕으로 데일리 리서치 리포트를 작성해줘."
    return ask_ai(prompt, system_prompt=system, want_json=False, max_tokens=1800)


def page_research_general():
    subtitle("리서치 · 종합")
    kr_items = get_multi_rss(FEEDS_DOMESTIC, limit_per_feed=6)
    gl_items = get_multi_rss(FEEDS_GLOBAL, limit_per_feed=6)
    context = "\n".join([f"- [{it['출처']}] {it['제목']}" for it in kr_items + gl_items])

    text, err = generate_research_report(context)
    if text:
        st.markdown(text)
        st.caption(f"AI 생성 리서치 리포트 · {datetime.now().strftime('%Y-%m-%d %H:%M')} 기준 헤드라인 참고 · "
                   "참고용, 투자판단 근거로 단독 사용 금지")
    else:
        st.info("AI 리포트를 쓰려면 Anthropic API 키가 필요합니다. 대신 증권사 시황정보 리포트 원문 목록을 보여드립니다.")
        render_research_list("market_info_list.naver", "시황정보")


def page_research_industry():
    subtitle("리서치 · 산업분석 (경기순환 관점)")

    st.markdown("**경기순환 4국면과 유리한 섹터**")
    cycle_df = pd.DataFrame([
        {"국면": "회복기 (저점→확장)", "특징": "금리 인하 마무리, 경기 바닥 확인", "유리한 섹터": "금융, 경기소비재, IT"},
        {"국면": "확장기", "특징": "성장률 상승, 기업이익 개선", "유리한 섹터": "산업재, 소재, 에너지"},
        {"국면": "후퇴기 (정점→수축)", "특징": "금리 인상, 성장 둔화 시작", "유리한 섹터": "필수소비재, 헬스케어"},
        {"국면": "침체기", "특징": "경기 저점 형성, 방어적 국면", "유리한 섹터": "유틸리티, 국채, 배당주"},
    ])
    st.dataframe(cycle_df, use_container_width=True, hide_index=True)
    st.caption("※ 일반적인 경기순환-섹터 로테이션 이론에 기반한 참고표이며, 실제 국면 판단과는 별개입니다.")

    st.markdown("---")
    st.markdown("**현재 경기 국면 — AI 판단**")
    if get_anthropic_client() is not None:
        system = (
            "당신은 거시경제 애널리스트입니다. 웹검색으로 최신 경제지표(고용, 물가, 금리, PMI 등) 뉴스를 확인해서, "
            "현재 한국과 미국이 경기순환상 어느 국면(회복기/확장기/후퇴기/침체기)에 가까운지 각각 2~3문장으로 "
            "근거와 함께 제시하세요. 확정적 예측이 아닌 참고 의견임을 전제로 하세요. 한국어로 작성하세요."
        )
        text, err = ask_ai("현재 한국과 미국의 경기 국면을 판단해줘.", system_prompt=system, max_tokens=600)
        if text:
            st.markdown(text)
            st.caption("AI 웹서치 기반 참고 의견 · 공식 지표가 아님")
        else:
            st.caption(f"조회 실패: {err}")
    else:
        st.caption("AI 판단을 쓰려면 Anthropic API 키가 필요합니다.")

    st.markdown("---")
    st.markdown("**공식 경기선행지수 원자료**")
    render_link_table([
        ("통계청 - 경기종합지수 (KOSIS)", "https://kosis.kr/statHtml/statHtml.do?orgId=101&tblId=DT_1C8015", "월간·무료"),
        ("OECD - Composite Leading Indicator", "https://www.oecd.org/en/data/indicators/composite-leading-indicator-cli.html", "월간·무료"),
        ("Conference Board - US LEI", "https://www.conference-board.org/topics/us-leading-indicators", "월간·무료"),
    ])


def page_research_strategy():
    subtitle("리서치 · 투자전략 (투자정보)")
    render_research_list("invest_list.naver", "투자정보")


def render_investor_table(trend):
    def row_html(label, d):
        return (f"<tr><td style='padding:5px 8px;'>{label}</td>"
                f"<td style='padding:5px 8px;text-align:right;'>{fmt_num(d['개인'])}</td>"
                f"<td style='padding:5px 8px;text-align:right;'>{fmt_num(d['외국인'])}</td>"
                f"<td style='padding:5px 8px;text-align:right;'>{fmt_num(d['기관'])}</td></tr>")
    html = (
        "<table style='width:100%;border-collapse:collapse;font-size:12.5px;'>"
        "<tr style='background:#f5f5f5;'>"
        "<th style='padding:5px 8px;text-align:left;'>구분</th>"
        "<th style='padding:5px 8px;text-align:right;'>개인</th>"
        "<th style='padding:5px 8px;text-align:right;'>외국인</th>"
        "<th style='padding:5px 8px;text-align:right;'>기관</th></tr>"
        + row_html(f"당일({trend['당일']['날짜']})", trend["당일"])
        + row_html("주간누계", trend["주간누계"])
        + row_html("월간누계", trend["월간누계"])
        + "</table>"
    )
    st.markdown(html, unsafe_allow_html=True)


@st.cache_data(ttl=60)
def debug_dump_table(url, max_rows=6):
    """진단용: 테이블의 각 행을 셀 텍스트 리스트 그대로 반환 (구조 파악용)"""
    from bs4 import BeautifulSoup
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    try:
        r = requests.get(url, headers=headers, timeout=6)
        r.encoding = "euc-kr"
        soup = BeautifulSoup(r.text, "html.parser")
        tables = soup.select("table")
        out = []
        for ti, table in enumerate(tables):
            cls = table.get("class", [])
            row_dump = []
            for tr in table.select("tr")[:max_rows]:
                cells = tr.find_all(["th", "td"])
                texts = [c.get_text(strip=True) for c in cells]
                if any(texts):
                    row_dump.append(texts)
            if row_dump:
                out.append({"table_index": ti, "class": cls, "rows": row_dump})
        return out
    except Exception as e:
        return [{"error": str(e)}]


def page_index_kr():
    subtitle("국내지수 및 업종")
    df = get_kr_indices()
    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "현재가": st.column_config.NumberColumn(format="%,.2f"),
            "전일대비": st.column_config.NumberColumn(format="%,.2f"),
            "등락률(%)": st.column_config.NumberColumn(format="%,.2f"),
            "거래량": st.column_config.NumberColumn(format="%,d"),
            "52주 최고": st.column_config.NumberColumn(format="%,.2f"),
            "52주 최저": st.column_config.NumberColumn(format="%,.2f"),
        },
    )

    c1, c2 = st.columns(2)
    for col, (label, code) in zip((c1, c2), [("코스피", "KOSPI"), ("코스닥", "KOSDAQ")]):
        with col:
            breadth = get_naver_market_breadth(code)
            if breadth:
                st.caption(f"{label} 상승 {breadth['상승']} · 보합 {breadth.get('보합','-')} · 하락 {breadth['하락']}")
            else:
                st.caption(f"{label} 상승/하락 종목수를 불러오지 못했습니다.")
    st.caption(f"업데이트: {datetime.now().strftime('%H:%M:%S')} · 출처: Yahoo Finance(yfinance) / 네이버금융")

    st.markdown("---")
    st.markdown("**수급현황 (투자자별 순매수, 억원)**")
    c1, c2 = st.columns(2)
    for col, (label, sosok) in zip((c1, c2), [("코스피", "0"), ("코스닥", "1")]):
        with col:
            trend = get_naver_investor_trend(sosok)
            if trend:
                st.markdown(f"**{label}**")
                render_investor_table(trend)
            else:
                st.caption(f"{label} 수급현황을 불러오지 못했습니다.")
    st.caption("출처: 네이버금융 · 단위 억원, 음수(빨간색)는 순매도")

    st.markdown("---")
    st.markdown("**업종별 시세**")
    all_sectors = get_naver_sector_list()
    if all_sectors:
        total_n = len(all_sectors)
        up_n = sum(1 for s in all_sectors if s["_등락률_값"] > 0)
        down_n = sum(1 for s in all_sectors if s["_등락률_값"] < 0)
        flat_n = total_n - up_n - down_n
        st.markdown(
            f"전체 **{total_n}개 업종** 중 <span style='color:#1a7a1a;'>상승 {up_n}개</span> · "
            f"보합 {flat_n}개 · <span style='color:#c22;'>하락 {down_n}개</span>",
            unsafe_allow_html=True
        )

        top20 = sorted(all_sectors, key=lambda s: s["_등락률_값"], reverse=True)[:20]
        display_df = pd.DataFrame([
            {"업종": s["업종"], "등락률(%)": s["등락률(%)"], "총 종목수": s["전체"],
             "상승": s["상승"], "보합": s["보합"], "하락": s["하락"]}
            for s in top20
        ])
        st.dataframe(display_df, use_container_width=True, hide_index=True)
        st.caption("상위 20개(등락률 기준) · 상세 전체 내역은 "
                   "[네이버금융 업종별시세](https://finance.naver.com/sise/sise_group.naver?type=upjong) 참조")
    else:
        st.caption("업종별 시세를 불러오지 못했습니다.")

    st.markdown("---")
    if st.checkbox("🔧 진단모드 (원본 데이터 구조 보기)", key="idx_debug"):
        st.caption("아래 내용을 캡처(또는 복사)해서 보내주시면 정확한 구조로 고칠 수 있습니다.")
        st.markdown("**업종별시세 원본**")
        st.json(debug_dump_table("https://finance.naver.com/sise/sise_group.naver?type=upjong", max_rows=5))

        st.markdown("**수급현황(stock.naver.com API) 원본 응답 — 하루치 전체**")
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                               "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Referer": "https://stock.naver.com/",
            }
            today = datetime.now()
            params = {
                "tradeType": "KRX",
                "marketType": "KOSPI",
                "bizdate": today.strftime("%Y%m%d"),
                "startIdx": 0,
                "pageSize": 1,
            }
            resp = requests.get("https://stock.naver.com/api/domestic/market/trend/daily",
                                 headers=headers, params=params, timeout=8)
            import json as _json
            try:
                pretty = _json.dumps(resp.json(), ensure_ascii=False, indent=2)
            except Exception:
                pretty = resp.text
            st.code(f"status_code: {resp.status_code}\n\n{pretty}")
        except Exception as e:
            st.error(f"진단 실패: {e}")


def page_index_us():
    subtitle("해외지수 및 업종")
    df = get_us_indices()
    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "현재가": st.column_config.NumberColumn(format="%,.2f"),
            "전일대비": st.column_config.NumberColumn(format="%,.2f"),
            "등락률(%)": st.column_config.NumberColumn(format="%,.2f"),
            "거래량": st.column_config.NumberColumn(format="%,d"),
            "52주 최고": st.column_config.NumberColumn(format="%,.2f"),
            "52주 최저": st.column_config.NumberColumn(format="%,.2f"),
        },
    )
    st.caption(f"업데이트: {datetime.now().strftime('%H:%M:%S')} · 출처: Yahoo Finance(yfinance)")

    st.markdown("---")
    st.markdown("**업종별 시세 (미국)**")
    st.caption("S&P 500을 11개 GICS 섹터로 나눈 SPDR Select Sector ETF의 당일 등락률로 섹터 동향을 근사한 것입니다.")
    sectors = get_us_sector_performance()
    if sectors:
        sector_df = pd.DataFrame(sorted(sectors, key=lambda s: (s["등락률(%)"] is None, -(s["등락률(%)"] or 0))))
        st.dataframe(
            sector_df,
            use_container_width=True,
            hide_index=True,
            column_config={"등락률(%)": st.column_config.NumberColumn(format="%,.2f")},
        )
    else:
        st.caption("섹터 데이터를 불러오지 못했습니다.")
    st.caption("출처: Yahoo Finance(yfinance), SPDR Select Sector ETF")


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
            # 1순위: 무료 야후파이낸스 검색 (키 불필요)
            resolved = resolve_ticker_free(q)
            if resolved:
                d2 = search_stock(resolved["ticker"])
                if "error" not in d2:
                    d = d2
                    resolved_note = f"'{q}' → **{resolved['name']} ({resolved['ticker']})** 로 자동 인식했습니다. (무료 검색)"

        if "error" in d and get_anthropic_client() is not None:
            # 2순위: 무료 검색도 실패했고 AI 키가 있으면 AI로 재시도
            with st.spinner("AI로 정확한 티커 확인 중..."):
                resolved = resolve_ticker_via_ai(q)
            if resolved:
                d2 = search_stock(resolved["ticker"])
                if "error" not in d2:
                    d = d2
                    resolved_note = f"AI가 '{q}' → **{resolved['name']} ({resolved['ticker']})** 로 자동 인식했습니다."

        if "error" in d:
            st.error(f"조회 실패: 종목을 찾지 못했습니다. (마지막 시도값: {q})")
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
    st.caption("출처: Yahoo Finance(yfinance) · 정확한 티커를 모르면 그냥 종목명을 입력하세요 (무료 자동 인식, API 키 불필요)")


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


def render_ai_chat_panel():
    """화면 우측에 항상 떠 있는 AI 대화 패널 (다른 메뉴를 보면서 동시에 사용 가능)"""

    # 대화창 폭 조절 슬라이더 — 패널 맨 위, 아주 작은 이탤릭체
    st.markdown(
        "<div style='font-size:9.5px;color:#bbb;font-style:italic;'>AI 대화창 폭</div>",
        unsafe_allow_html=True
    )
    if "chat_pct" not in st.session_state:
        st.session_state.chat_pct = 25
    st.slider("AI 대화창 폭", min_value=15, max_value=45, step=5, key="chat_pct", label_visibility="collapsed")

    st.markdown("<div style='font-weight:700;font-size:14px;color:#c05a00;margin:4px 0 8px;'>🤖 AI 대화</div>", unsafe_allow_html=True)

    has_key = get_anthropic_client() is not None

    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []

    # 답변/질문 이력 — 경계가 뚜렷한 박스, 대화가 이어질수록 예전 내용이 위로 밀려 올라감
    chat_box = st.container(height=380, border=True)
    with chat_box:
        if st.session_state.chat_history:
            for role, msg in st.session_state.chat_history:
                with st.chat_message(role):
                    st.markdown(msg)
        else:
            st.markdown(
                "<div style='color:#ccc;font-size:12px;text-align:center;margin-top:150px;'>대화 내용이 여기 표시됩니다</div>",
                unsafe_allow_html=True
            )

    # 질문 입력창 — 답변창 바로 아래
    q = st.chat_input("무엇이든 물어보세요", key="ai_panel_input", disabled=not has_key)
    if q and has_key:
        st.session_state.chat_history.append(("user", q))
        system = (
            "당신은 이 투자정보 터미널 앱의 AI 비서입니다. 필요시 웹검색을 사용해 최신 정보로 "
            "간결하고 정확하게 한국어로 답하세요. 종목명을 물으면 정확한 티커(Yahoo Finance 기준, "
            "한국 종목은 .KS/.KQ 접미사)도 함께 알려주세요. 투자 조언이 아닌 정보 제공 목적임을 "
            "인지하고, 확정적인 매수/매도 추천은 하지 마세요. 답변은 패널이 좁으니 간결하게 작성하세요."
        )
        answer, err = ask_ai(q, system_prompt=system, max_tokens=800)
        st.session_state.chat_history.append(("assistant", answer if answer else f"오류: {err}"))
        st.rerun()

    if st.session_state.chat_history:
        if st.button("대화 초기화", key="ai_panel_reset", use_container_width=True):
            st.session_state.chat_history = []
            st.rerun()

    # 안내 문구 — 맨 아래, 아주 작은 이탤릭체
    if has_key:
        hint = "예: 'SK하이닉스 티커가 뭐야?'"
    else:
        hint = ('AI 대화를 쓰려면 Anthropic API 키가 필요합니다. Streamlit Cloud → Manage app → '
                'Settings → Secrets 에 ANTHROPIC_API_KEY = "sk-ant-..." 추가')
    st.markdown(
        f"<div style='font-size:10px;color:#bbb;font-style:italic;margin-top:8px;'>{hint}</div>",
        unsafe_allow_html=True
    )


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
        "국내지수 및 업종": page_index_kr,
        "해외지수 및 업종": page_index_us,
        "환율": page_fx,
        "종목 조회": page_stock_search,
    },
    "🏛️ 정책/일정": {
        "미국": page_policy_us,
        "한국": page_policy_kr,
    },
}

# ─────────────────────────────────────────────
# 사이드바 렌더 + 라우팅 (대분류를 폴더처럼 펼쳐서 하위 항목 클릭)
# ─────────────────────────────────────────────
if "page" not in st.session_state:
    st.session_state.page = ("🗞️ 브리핑", "브리핑")

for major, minors in MENU.items():
    is_current_group = st.session_state.page[0] == major
    with st.sidebar.expander(f"**{major}**", expanded=is_current_group):
        for minor in minors:
            is_active = (major, minor) == st.session_state.page
            label = f"**● {minor}**" if is_active else f"**{minor}**"
            if st.button(label, key=f"nav-{major}-{minor}", use_container_width=True):
                st.session_state.page = (major, minor)
                st.rerun()

# ─────────────────────────────────────────────
# 본문: 좌측(선택 메뉴) + 우측(AI 대화 상시 패널, 폭 조절은 패널 내부 슬라이더로)
# ─────────────────────────────────────────────
chat_pct = st.session_state.get("chat_pct", 25)
col_main, col_chat = st.columns([100 - chat_pct, chat_pct])

with col_main:
    st.markdown("<div class='app-title'>📊 투자 정보 터미널</div>", unsafe_allow_html=True)
    major, minor = st.session_state.page
    major_text = major.split(" ", 1)[-1] if " " in major else major  # 이모지 제거한 순수 텍스트
    title = major if minor == major_text else f"{major} · {minor}"
    st.markdown(f"<div class='page-title'>{title}</div>", unsafe_allow_html=True)
    MENU[major][minor]()

with col_chat:
    st.markdown(
        "<div style='border-left:1px solid #e0e0e0;padding-left:14px;'>",
        unsafe_allow_html=True
    )
    render_ai_chat_panel()
    st.markdown("</div>", unsafe_allow_html=True)
