from __future__ import annotations

import datetime as dt
import html
import json
import re
import urllib.parse
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import List, Dict

import pandas as pd
import requests
from pykrx import stock

ROOT = Path(__file__).resolve().parent.parent
REPORT_DIR = ROOT / "reports"
INDEX_FILE = ROOT / "index.html"
SITEMAP_FILE = ROOT / "sitemap.xml"
REPORT_META_FILE = REPORT_DIR / "report_index.json"

SITE_NAME = "K-Stock Daily Pulse"
SITE_URL = "https://pre-visual.web.app"
ADSENSE_CLIENT = "ca-pub-6025469498161210"
NEWS_CACHE: Dict[str, List[Dict[str, str]]] = {}
NEWS_LOOKBACK_DAYS = 3
NEWS_TOP_LIMIT = 5
MAX_NEWS_PER_STOCK = 3
TRUSTED_NEWS_SOURCES = {
    "연합뉴스",
    "뉴시스",
    "머니투데이",
    "한국경제",
    "매일경제",
    "서울경제",
    "이데일리",
    "아시아경제",
    "파이낸셜뉴스",
    "한국경제TV",
    "뉴스1",
    "조선비즈",
    "전자신문",
    "헤럴드경제",
    "딜사이트",
    "Chosunbiz",
}
SOURCE_ALIAS = {
    "chosunbiz": "Chosunbiz",
    "조선비즈": "Chosunbiz",
    "매경닷컴": "매일경제",
    "mk.co.kr": "매일경제",
}


def fmt_int(v: float) -> str:
    return f"{int(v):,}"


def stock_comment(rate: float, turnover: float, median_turnover: float) -> str:
    if rate >= 20:
        trend = "급등 강세"
    elif rate >= 10:
        trend = "강한 상승"
    elif rate >= 5:
        trend = "상승 우위"
    elif rate <= -20:
        trend = "급락 약세"
    elif rate <= -10:
        trend = "강한 하락"
    elif rate <= -5:
        trend = "하락 우위"
    else:
        trend = "보합권 이탈"

    if median_turnover > 0 and turnover >= median_turnover * 5:
        flow = "거래대금 집중"
    elif median_turnover > 0 and turnover >= median_turnover * 2:
        flow = "거래 유입"
    else:
        flow = "거래 평이"

    return f"{trend} · {flow}"


def quant_reason(rate: float, turnover: float, median_turnover: float, direction: str) -> str:
    if direction == "up":
        if rate >= 20:
            momentum = "상한가권 급등"
        elif rate >= 10:
            momentum = "강한 상승 탄력"
        else:
            momentum = "상승 흐름 유지"
    else:
        if rate <= -20:
            momentum = "급락 구간 진입"
        elif rate <= -10:
            momentum = "강한 하락 압력"
        else:
            momentum = "하락세 지속"

    if median_turnover > 0 and turnover >= median_turnover * 5:
        flow = "평균 대비 거래대금이 크게 확대"
    elif median_turnover > 0 and turnover >= median_turnover * 2:
        flow = "거래대금이 평균 대비 유의미하게 증가"
    else:
        flow = "거래대금은 평균 수준"

    return f"{momentum}. {flow}되어 수급 영향이 크게 반영된 흐름으로 해석됩니다."


def fetch_related_news(stock_name: str, report_day: dt.date, direction: str) -> List[Dict[str, str]]:
    cache_key = f"{stock_name}|{report_day.isoformat()}|{direction}"
    if cache_key in NEWS_CACHE:
        return NEWS_CACHE[cache_key]

    after = (report_day - dt.timedelta(days=2)).strftime("%Y-%m-%d")
    before = (report_day + dt.timedelta(days=1)).strftime("%Y-%m-%d")
    keyword = "급등 OR 상승 OR 실적 OR 수주 OR 계약" if direction == "up" else "급락 OR 하락 OR 악재 OR 리스크 OR 실적"
    query = f"\"{stock_name}\" {keyword} after:{after} before:{before}"
    encoded = urllib.parse.quote(query)
    url = f"https://news.google.com/rss/search?q={encoded}&hl=ko&gl=KR&ceid=KR:ko"

    try:
        resp = requests.get(url, timeout=8)
        resp.raise_for_status()
        root = ET.fromstring(resp.text)
    except Exception:
        NEWS_CACHE[cache_key] = []
        return []

    def normalize_source_name(source: str) -> str:
        s = source.strip()
        if not s:
            return ""
        return SOURCE_ALIAS.get(s.lower(), SOURCE_ALIAS.get(s, s))

    def split_title_source(title: str) -> tuple[str, str]:
        # Google News RSS title is often "<headline> - <publisher>"
        if " - " in title:
            h, src = title.rsplit(" - ", 1)
            return h.strip(), src.strip()
        return title.strip(), ""

    direction_words = {"up": ["급등", "상승", "호재", "실적", "수주", "계약"], "down": ["급락", "하락", "악재", "리스크", "우려", "적자"]}
    candidates = []
    for item in root.findall("./channel/item"):
        title = item.findtext("title", "").strip()
        link = item.findtext("link", "").strip()
        pub_date = item.findtext("pubDate", "").strip()
        source_el = item.find("source")
        source = source_el.text.strip() if source_el is not None and source_el.text else ""
        if not title or not link:
            continue

        headline, suffix_source = split_title_source(title)
        source = normalize_source_name(source or suffix_source)
        score = 0
        if stock_name in headline:
            score += 4
        if any(w in headline for w in direction_words[direction]):
            score += 2
        if source in TRUSTED_NEWS_SOURCES:
            score += 3

        candidates.append(
            {
                "title": headline,
                "link": link,
                "pub_date": pub_date,
                "source": source,
                "score": score,
            }
        )

    # 우선순위 정렬 후 중복 헤드라인 제거
    candidates.sort(key=lambda x: x["score"], reverse=True)
    seen_titles = set()
    items = []
    for c in candidates:
        norm = c["title"].strip().lower()
        if norm in seen_titles:
            continue
        seen_titles.add(norm)
        # 화이트리스트 매체만 통과
        if c["source"] not in TRUSTED_NEWS_SOURCES:
            continue
        # 지나치게 연관성이 낮은 뉴스는 제외
        if c["score"] < 2:
            continue
        items.append(
            {
                "title": c["title"],
                "link": c["link"],
                "pub_date": c["pub_date"],
                "source": c["source"],
            }
        )
        if len(items) >= MAX_NEWS_PER_STOCK:
            break

    NEWS_CACHE[cache_key] = items
    return items


def build_deep_cards(
    sub: pd.DataFrame,
    direction: str,
    report_day: dt.date,
    latest_day: dt.date,
    median_turnover: float,
) -> str:
    cards = []
    can_search_news = (latest_day - report_day).days <= NEWS_LOOKBACK_DAYS
    for i, (_, r) in enumerate(sub.head(10).iterrows(), start=1):
        name = str(r["종목명"])
        ticker = str(r["티커"])
        rate = float(r["등락률"])
        turnover = float(r["거래대금"])
        news_items = []
        if can_search_news and i <= NEWS_TOP_LIMIT:
            news_items = fetch_related_news(name, report_day, direction)
        base_reason = quant_reason(rate, turnover, median_turnover, direction)

        if news_items:
            headline = news_items[0]["title"]
            reason = f"{base_reason} 관련 기사에서는 \"{headline}\" 이슈가 함께 관찰됩니다."
            links = "".join(
                f"<li><a href=\"{html.escape(n['link'])}\" target=\"_blank\" rel=\"noopener\">{html.escape(n['title'])}</a>"
                + (f" <span class=\"news-source\">({html.escape(n['source'])})</span>" if n.get("source") else "")
                + "</li>"
                for n in news_items
            )
            news_html = f"<ul class=\"news-links\">{links}</ul>"
        else:
            reason = f"{base_reason} 현재 자동 수집된 연관 뉴스는 확인되지 않았습니다."
            news_html = ""

        cards.append(
            "<article class=\"insight-card\">"
            f"<h4>{i}. {html.escape(name)} <span>({html.escape(ticker)}, {rate:.2f}%)</span></h4>"
            f"<p>{html.escape(reason)}</p>"
            f"{news_html}"
            "</article>"
        )
    return "".join(cards)


def enrich(df: pd.DataFrame) -> pd.DataFrame:
    names = {ticker: stock.get_market_ticker_name(ticker) for ticker in df.index}
    out = df.copy()
    out["티커"] = out.index
    out["종목명"] = out.index.map(names)
    return out


def page_template(title: str, description: str, body: str) -> str:
    return f"""<!doctype html>
<html lang=\"ko\">
  <head>
    <meta charset=\"UTF-8\" />
    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\" />
    <meta name=\"google-adsense-account\" content=\"{ADSENSE_CLIENT}\" />
    <meta name=\"description\" content=\"{description}\" />
    <title>{title}</title>
    <link rel=\"preconnect\" href=\"https://fonts.googleapis.com\" />
    <link rel=\"preconnect\" href=\"https://fonts.gstatic.com\" crossorigin />
    <link href=\"https://fonts.googleapis.com/css2?family=Merriweather:wght@700;900&family=Source+Sans+3:wght@400;600;700&display=swap\" rel=\"stylesheet\" />
    <link rel=\"stylesheet\" href=\"/style.css\" />
    <script async src=\"https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client={ADSENSE_CLIENT}\" crossorigin=\"anonymous\"></script>
  </head>
  <body>
    {body}
  </body>
</html>
"""


def build_day_report(
    day: dt.date,
    latest_day: dt.date,
    rank: int,
    total_days: int,
    prev_day: dt.date | None,
    next_day: dt.date | None,
) -> Dict[str, str]:
    d = day.strftime("%Y%m%d")
    label = day.strftime("%Y-%m-%d")
    df_kospi = stock.get_market_ohlcv_by_ticker(d, market="KOSPI")
    df_kosdaq = stock.get_market_ohlcv_by_ticker(d, market="KOSDAQ")
    df = pd.concat([df_kospi, df_kosdaq], axis=0)
    df = enrich(df)

    # 거래 정지/초저유동성/비정상 급등락(권리락·병합 등 특수 케이스) 제외
    df = df[(df["거래량"] >= 1000) & (df["등락률"] <= 30) & (df["등락률"] >= -30)].copy()

    gainers = df.sort_values("등락률", ascending=False).head(30).copy()
    losers = df.sort_values("등락률", ascending=True).head(30).copy()

    median_turnover = float(df["거래대금"].median())
    for sub in (gainers, losers):
        sub["코멘트"] = sub.apply(
            lambda r: stock_comment(float(r["등락률"]), float(r["거래대금"]), median_turnover), axis=1
        )
    gainers_deep = build_deep_cards(gainers, "up", day, latest_day, median_turnover)
    losers_deep = build_deep_cards(losers, "down", day, latest_day, median_turnover)

    adv = int((df["등락률"] > 0).sum())
    dec = int((df["등락률"] < 0).sum())
    flat = int((df["등락률"] == 0).sum())
    total_turnover = float(df["거래대금"].sum())
    top_focus = float(gainers.head(5)["거래대금"].sum()) / total_turnover * 100 if total_turnover else 0.0

    def to_rows(sub: pd.DataFrame, direction: str) -> str:
        rows = []
        for i, (_, r) in enumerate(sub.iterrows(), start=1):
            rate = float(r["등락률"])
            rate_cls = "rate-up" if direction == "up" else "rate-down"
            rows.append(
                "<tr>"
                f"<td>{i}</td>"
                f"<td><div class=\"stock-main\">{r['종목명']} <span class=\"rate-badge {rate_cls}\">{rate:.2f}%</span></div></td>"
                f"<td>{r['티커']}</td>"
                f"<td>{fmt_int(r['종가'])}</td>"
                f"<td>{fmt_int(r['거래량'])}</td>"
                f"<td>{fmt_int(r['거래대금'])}</td>"
                f"<td>{r['코멘트']}</td>"
                "</tr>"
            )
        return "\n".join(rows)

    def to_mobile_cards(sub: pd.DataFrame, direction: str) -> str:
        cards = []
        for i, (_, r) in enumerate(sub.iterrows(), start=1):
            rate = float(r["등락률"])
            rate_cls = "rate-up" if direction == "up" else "rate-down"
            cards.append(
                "<article class=\"mobile-item\">"
                f"<p class=\"mobile-top\"><strong>{i}. {r['종목명']}</strong> <span class=\"rate-badge {rate_cls}\">{rate:.2f}%</span></p>"
                f"<p class=\"mobile-meta\">티커 {r['티커']} · 종가 {fmt_int(r['종가'])}원</p>"
                f"<p class=\"mobile-meta\">거래량 {fmt_int(r['거래량'])} · 거래대금 {fmt_int(r['거래대금'])}원</p>"
                f"<p class=\"mobile-comment\">{r['코멘트']}</p>"
                "</article>"
            )
        return "\n".join(cards)

    prev_link = f"/reports/{prev_day.strftime('%Y-%m-%d')}.html" if prev_day else "#"
    next_link = f"/reports/{next_day.strftime('%Y-%m-%d')}.html" if next_day else "#"
    prev_class = "" if prev_day else " disabled"
    next_class = "" if next_day else " disabled"

    body = f"""
<header class=\"site-header\">
  <div class=\"header-inner\">
    <a class=\"brand\" href=\"/\">{SITE_NAME}</a>
    <nav class=\"site-nav\" aria-label=\"리포트 메뉴\">
      <a href=\"/\">리포트 허브</a>
      <a href=\"/privacy.html\">개인정보처리방침</a>
      <a href=\"/terms.html\">이용약관</a>
    </nav>
  </div>
</header>

<main class=\"app\">
  <section class=\"hero\">
    <p class=\"kicker\">KOREA MARKET DAILY REPORT</p>
    <h1>{label} KOSPI/KOSDAQ 데일리 마켓 브리프</h1>
    <p class=\"desc\">누적 아카이브 기준 {rank}/{total_days} 페이지. 당일 전체 종목의 등락률 분포에서 상승/하락 상위 30개를 추출해 정리했습니다.</p>
    <p class=\"meta-line\">상승 {adv}개 · 하락 {dec}개 · 보합 {flat}개 · 상위 5개 거래대금 집중도 {top_focus:.2f}%</p>
    <div class=\"pager\">
      <a class=\"pager-link{prev_class}\" href=\"{prev_link}\">이전 거래일</a>
      <a class=\"pager-link\" href=\"/\">목록</a>
      <a class=\"pager-link{next_class}\" href=\"{next_link}\">다음 거래일</a>
    </div>
  </section>

  <section class=\"panel\">
    <h2>상승 상위 30</h2>
    <div class=\"table-wrap\">
      <table>
        <thead>
          <tr><th>순위</th><th>종목명/등락률</th><th>티커</th><th>종가(원)</th><th>거래량</th><th>거래대금(원)</th><th>해석</th></tr>
        </thead>
        <tbody>
          {to_rows(gainers, "up")}
        </tbody>
      </table>
    </div>
    <div class=\"mobile-list\">
      {to_mobile_cards(gainers, "up")}
    </div>
  </section>

  <section class=\"panel\">
    <h2>하락 상위 30</h2>
    <div class=\"table-wrap\">
      <table>
        <thead>
          <tr><th>순위</th><th>종목명/등락률</th><th>티커</th><th>종가(원)</th><th>거래량</th><th>거래대금(원)</th><th>해석</th></tr>
        </thead>
        <tbody>
          {to_rows(losers, "down")}
        </tbody>
      </table>
    </div>
    <div class=\"mobile-list\">
      {to_mobile_cards(losers, "down")}
    </div>
  </section>

  <section class=\"panel\">
    <h2>데일리 해석</h2>
    <ul class=\"policy-list\">
      <li>당일 등락률은 장마감 기준이며 실시간 변동과 다를 수 있습니다.</li>
      <li>상승/하락 종목은 시장 전체 흐름과 개별 이슈의 영향을 동시에 받습니다.</li>
      <li>본 자료는 투자 권유가 아닌 정보 제공용 요약입니다.</li>
    </ul>
  </section>

  <section class=\"panel\">
    <h2>상승 종목 구체 분석 + 관련 뉴스</h2>
    <div class=\"insight-grid\">
      {gainers_deep}
    </div>
  </section>

  <section class=\"panel\">
    <h2>하락 종목 구체 분석 + 관련 뉴스</h2>
    <div class=\"insight-grid\">
      {losers_deep}
    </div>
  </section>

  <footer class=\"site-footer\">
    <p>데이터 출처: KRX 일별 시세(수집 시점 기준)</p>
    <p>면책: 본 페이지는 투자 자문이 아닙니다.</p>
  </footer>
</main>
"""

    html = page_template(
        title=f"{label} 한국주식 상승·하락 30 분석 | {SITE_NAME}",
        description=f"{label} 한국 주식시장 상승 30개와 하락 30개 종목을 거래량/거래대금과 함께 분석한 리포트",
        body=body,
    )

    strongest = gainers.iloc[0]
    weakest = losers.iloc[0]

    return {
        "date": label,
        "path": f"reports/{label}.html",
        "html": html,
        "strong": f"{strongest['종목명']} ({float(strongest['등락률']):.2f}%)",
        "weak": f"{weakest['종목명']} ({float(weakest['등락률']):.2f}%)",
        "advance": adv,
        "decline": dec,
        "flat": flat,
        "top_focus": round(top_focus, 2),
    }


def build_index(reports: List[Dict[str, str]]) -> str:
    cards = []
    sorted_reports = sorted(reports, key=lambda x: x["date"], reverse=True)
    latest = sorted_reports[0] if sorted_reports else None

    for r in sorted_reports:
        cards.append(
            f"""
<article class=\"report-card\">
  <h3><a href=\"/{r['path']}\">{r['date']} 주식장 분석</a></h3>
  <p>상승 대표: {r['strong']}</p>
  <p>하락 대표: {r['weak']}</p>
  <p>상승/하락/보합: {r.get('advance', '-')} / {r.get('decline', '-')} / {r.get('flat', '-')}</p>
  <a class=\"read-link\" href=\"/{r['path']}\">하루치 상세 보기</a>
</article>
"""
        )

    latest_box = ""
    if latest:
        latest_box = f"""
  <section class=\"panel metrics-panel\">
    <h2>최신 리포트 핵심 지표 ({latest['date']})</h2>
    <div class=\"metric-grid\">
      <div class=\"metric-card\"><span>상승 종목</span><strong>{latest.get('advance', '-')}</strong></div>
      <div class=\"metric-card\"><span>하락 종목</span><strong>{latest.get('decline', '-')}</strong></div>
      <div class=\"metric-card\"><span>보합 종목</span><strong>{latest.get('flat', '-')}</strong></div>
      <div class=\"metric-card\"><span>상위 5개 거래집중</span><strong>{latest.get('top_focus', '-')}%</strong></div>
    </div>
  </section>
"""

    body = f"""
<header class=\"site-header\">
  <div class=\"header-inner\">
    <a class=\"brand\" href=\"/\">{SITE_NAME}</a>
    <nav class=\"site-nav\" aria-label=\"주요 메뉴\">
      <a href=\"#reports\">누적 리포트 아카이브</a>
      <a href=\"/privacy.html\">개인정보처리방침</a>
      <a href=\"/terms.html\">이용약관</a>
    </nav>
  </div>
</header>

<main class=\"app\">
  <section class=\"hero\">
    <p class=\"kicker\">EQUITY RESEARCH NOTE</p>
    <h1>한국 주식 일일 모멘텀 아카이브</h1>
    <p class=\"desc\">장마감 데이터를 기반으로 KOSPI/KOSDAQ 상승 상위 30, 하락 상위 30을 매일 축적합니다. 과거 리포트는 삭제되지 않고 누적 보관됩니다.</p>
    <p class=\"meta-line\">누적 리포트 수: {len(sorted_reports)}개 · 최신 업데이트: {dt.date.today().strftime('%Y-%m-%d')}</p>
  </section>

  {latest_box}

  <section id=\"reports\" class=\"panel\">
    <h2>누적 일자별 리포트</h2>
    <div class=\"cards\">
      {''.join(cards)}
    </div>
  </section>

  <section class=\"panel\">
    <h2>안내</h2>
    <ul class=\"policy-list\">
      <li>리포트는 장마감 데이터 기반 자동 생성입니다.</li>
      <li>종목 코멘트는 등락률과 거래대금 강도를 기준으로 한 요약 텍스트입니다.</li>
      <li>본 사이트는 투자 권유를 제공하지 않습니다.</li>
    </ul>
  </section>

  <footer class=\"site-footer\">
    <p>데이터 출처: KRX 일별 시세(수집 시점 기준)</p>
    <p><a href=\"/privacy.html\">개인정보처리방침</a> | <a href=\"/terms.html\">이용약관</a></p>
    <p>최종 생성일: {dt.date.today().strftime('%Y-%m-%d')}</p>
  </footer>
</main>
"""

    return page_template(
        title=f"{SITE_NAME} | 최근 2주 한국 주식 상승·하락 30 분석",
        description="최근 2주 한국 주식시장의 일자별 상승 30개, 하락 30개 종목 분석 블로그",
        body=body,
    )


def build_sitemap(report_paths: List[str]) -> str:
    urls = [
        "/",
        "/privacy.html",
        "/terms.html",
        *[f"/{p}" for p in report_paths],
    ]

    rows = []
    for u in urls:
        rows.append(
            "  <url>\n"
            f"    <loc>{SITE_URL}{u}</loc>\n"
            "    <changefreq>daily</changefreq>\n"
            "    <priority>0.8</priority>\n"
            "  </url>"
        )
    return "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n<urlset xmlns=\"http://www.sitemaps.org/schemas/sitemap/0.9\">\n" + "\n".join(rows) + "\n</urlset>\n"


def load_existing_meta() -> Dict[str, Dict[str, str]]:
    if not REPORT_META_FILE.exists():
        return {}

    try:
        raw = json.loads(REPORT_META_FILE.read_text(encoding="utf-8"))
        if isinstance(raw, dict):
            return raw
    except Exception:
        pass
    return {}


def discover_report_dates() -> List[str]:
    dates = []
    for f in REPORT_DIR.glob("*.html"):
        m = re.fullmatch(r"(\d{4}-\d{2}-\d{2})\.html", f.name)
        if m:
            dates.append(m.group(1))
    return sorted(set(dates))


def compact_meta(record: Dict[str, str]) -> Dict[str, str]:
    return {
        "date": record.get("date", "-"),
        "path": record.get("path", ""),
        "strong": record.get("strong", "-"),
        "weak": record.get("weak", "-"),
        "advance": record.get("advance", "-"),
        "decline": record.get("decline", "-"),
        "flat": record.get("flat", "-"),
        "top_focus": record.get("top_focus", "-"),
    }


def main() -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    report_meta = load_existing_meta()

    today = dt.date.today()
    start = today - dt.timedelta(days=20)
    biz_days = stock.get_previous_business_days(fromdate=start, todate=today)
    target_days = biz_days[-10:]

    for i, day in enumerate(target_days):
        prev_day = target_days[i - 1] if i > 0 else None
        next_day = target_days[i + 1] if i + 1 < len(target_days) else None
        latest_day = target_days[-1]
        report = build_day_report(day, latest_day, i + 1, len(target_days), prev_day, next_day)
        (REPORT_DIR / f"{report['date']}.html").write_text(report["html"], encoding="utf-8")
        report_meta[report["date"]] = {
            "date": report["date"],
            "path": report["path"],
            "strong": report["strong"],
            "weak": report["weak"],
            "advance": report["advance"],
            "decline": report["decline"],
            "flat": report["flat"],
            "top_focus": report["top_focus"],
        }

    # 누락된 메타는 최소 정보로 보완
    for d in discover_report_dates():
        if d not in report_meta:
            report_meta[d] = {
                "date": d,
                "path": f"reports/{d}.html",
                "strong": "-",
                "weak": "-",
                "advance": "-",
                "decline": "-",
                "flat": "-",
                "top_focus": "-",
            }

    reports = [compact_meta(report_meta[d]) for d in sorted(report_meta.keys())]

    INDEX_FILE.write_text(build_index(reports), encoding="utf-8")
    SITEMAP_FILE.write_text(build_sitemap([r["path"] for r in reports]), encoding="utf-8")
    REPORT_META_FILE.write_text(
        json.dumps({r["date"]: r for r in reports}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print("generated", len(reports), "daily report pages")
    print("days", ", ".join(r["date"] for r in reports))


if __name__ == "__main__":
    main()
