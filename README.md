# 투자 정보 터미널 (Streamlit)

## 로컬 실행
```bash
pip install -r requirements.txt
streamlit run app.py
```
브라우저에서 http://localhost:8501 자동 오픈

## 메뉴 구조
- 🗞️ 브리핑 → AI 서술형 종합 브리핑 (Anthropic API 키 필요, 없으면 헤드라인 목록으로 대체)
- 📡 최신 뉴스 → 국내 뉴스 / 해외 뉴스 (RSS)
- 🔎 리서치 → 종합 / 기업분석 / 산업분석 / 투자전략 (네이버금융 리서치, 증권사 애널리스트 리포트)
- 📈 실시간 시황 → 국내 지수 / 해외 지수 / 환율 / 종목 조회
- 🏛️ 정책/일정 → 미국 / 한국 (현재 수동, 추후 자동화 예정)

## AI 브리핑용 API 키 설정 (Streamlit Cloud)
1. https://console.anthropic.com 에서 API 키 발급 (사용량만큼 소액 과금)
2. Streamlit Cloud → 앱 → Manage app → Settings → Secrets 에 추가:
```
ANTHROPIC_API_KEY = "sk-ant-여기에키입력"
```
3. 저장하면 앱이 자동 재시작되며 브리핑이 AI 서술형으로 전환됩니다.
키를 넣지 않으면 브리핑 메뉴는 자동으로 헤드라인 목록 방식으로 대체됩니다.

## 접근 제한 (비밀번호 게이트)
링크를 아는 사람만 들어오게 하려면 Streamlit Cloud → Manage app → Settings → Secrets 에 추가:
```
APP_PASSWORD = "원하는비밀번호"
```
설정하면 앱 진입 시 비밀번호 입력창이 먼저 뜨고, 맞는 비밀번호를 입력해야 이후 화면이 보입니다.
설정하지 않으면 기존처럼 제한 없이 바로 사용 가능합니다.
(참고: Streamlit Cloud의 "Private app + 이메일 초대" 기능과 별개이며, 둘 중 하나만 써도 되고 둘 다 같이 써도 됩니다.)

새 메뉴 추가 방법: `app.py`의 `MENU` 딕셔너리에 `"중분류명": 렌더함수` 한 줄만 추가

## 무료 데이터 출처
| 항목 | 출처 | 비고 |
|---|---|---|
| 해외 지수/종목 | yfinance (Yahoo Finance) | 비공식 API, 가끔 지연/차단 가능 |
| 국내 지수 | FinanceDataReader | 무료, 키 불필요 |
| 환율 | frankfurter.app | ECB 기준, 무료, 키 불필요 |
| 뉴스 | 각 언론사 RSS | 공개 RSS 피드 사용 |
| 정책 일정 | 현재 수동 | 추후 Fed/한국은행 공식 캘린더 크롤링으로 자동화 |

## Streamlit Community Cloud 무료 배포
1. GitHub에 이 폴더(app.py, requirements.txt) 저장소로 업로드
2. https://share.streamlit.io 접속 → GitHub 계정 연동
3. 저장소 선택 → app.py 지정 → Deploy
4. 배포된 URL로 어디서든(claude.ai 없이) 접속 가능
