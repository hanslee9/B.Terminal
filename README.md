# 투자 정보 터미널 (Streamlit)

## 로컬 실행
```bash
pip install -r requirements.txt
streamlit run app.py
```
브라우저에서 http://localhost:8501 자동 오픈

## 메뉴 구조
- 📰 뉴스브리핑 → 국내 뉴스 / 해외 뉴스 (RSS)
- 📈 실시간 시황 → 국내 지수 / 해외 지수 / 환율 / 종목 조회
- 🏛️ 정책/일정 → 미국 / 한국 (현재 수동, 추후 자동화 예정)

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
