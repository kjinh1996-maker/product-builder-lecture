from __future__ import annotations

import datetime as dt
from pathlib import Path
from typing import List, Dict

import pandas as pd
from pykrx import stock

ROOT = Path(__file__).resolve().parent.parent
REPORT_DIR = ROOT / "reports"
INDEX_FILE = ROOT / "index.html"
SITEMAP_FILE = ROOT / "sitemap.xml"

SITE_NAME = "K-Stock Daily Pulse"
SITE_URL = "https://pre-visual.web.app"
ADSENSE_CLIENT = "ca-pub-6025469498161210"


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
    <link href=\"https://fonts.googleapis.com/css2?family=Do+Hyeon&family=Noto+Sans+KR:wght@400;600;700&display=swap\" rel=\"stylesheet\" />
    <link rel=\"stylesheet\" href=\"/style.css\" />
    <script async src=\"https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client={ADSENSE_CLIENT}\" crossorigin=\"anonymous\"></script>
  </head>
  <body>
    {body}
  </body>
</html>
"""


def build_day_report(day: dt.date, rank: int, total_days: int, prev_day: dt.date | None, next_day: dt.date | None) -> Dict[str, str]:
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

    adv = int((df["등락률"] > 0).sum())
    dec = int((df["등락률"] < 0).sum())
    flat = int((df["등락률"] == 0).sum())
    total_turnover = float(df["거래대금"].sum())
    top_focus = float(gainers.head(5)["거래대금"].sum()) / total_turnover * 100 if total_turnover else 0.0

    def to_rows(sub: pd.DataFrame) -> str:
        rows = []
        for i, (_, r) in enumerate(sub.iterrows(), start=1):
            rows.append(
                "<tr>"
                f"<td>{i}</td>"
                f"<td>{r['종목명']}</td>"
                f"<td>{r['티커']}</td>"
                f"<td>{fmt_int(r['종가'])}</td>"
                f"<td>{float(r['등락률']):.2f}%</td>"
                f"<td>{fmt_int(r['거래량'])}</td>"
                f"<td>{fmt_int(r['거래대금'])}</td>"
                f"<td>{r['코멘트']}</td>"
                "</tr>"
            )
        return "\n".join(rows)

    prev_link = f"/reports/{prev_day.strftime('%Y-%m-%d')}.html" if prev_day else "#"
    next_link = f"/reports/{next_day.strftime('%Y-%m-%d')}.html" if next_day else "#"
    prev_class = "" if prev_day else " disabled"
    next_class = "" if next_day else " disabled"

    body = f"""
<header class=\"site-header\">
  <div class=\"header-inner\">
    <a class=\"brand\" href=\"/\">{SITE_NAME}</a>
    <nav class=\"site-nav\" aria-label=\"리포트 메뉴\">
      <a href=\"/\">최근 2주 목록</a>
      <a href=\"/privacy.html\">개인정보처리방침</a>
      <a href=\"/terms.html\">이용약관</a>
    </nav>
  </div>
</header>

<main class=\"app\">
  <section class=\"hero\">
    <p class=\"kicker\">KOREA MARKET DAILY REPORT</p>
    <h1>{label} 상승/하락 30 종목 분석</h1>
    <p class=\"desc\">최근 2주 리포트 중 {rank}/{total_days} 페이지. 전 종목 일일 등락률 기준으로 상위/하위 30개를 정리했습니다.</p>
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
          <tr><th>순위</th><th>종목명</th><th>티커</th><th>종가(원)</th><th>등락률</th><th>거래량</th><th>거래대금(원)</th><th>해석</th></tr>
        </thead>
        <tbody>
          {to_rows(gainers)}
        </tbody>
      </table>
    </div>
  </section>

  <section class=\"panel\">
    <h2>하락 상위 30</h2>
    <div class=\"table-wrap\">
      <table>
        <thead>
          <tr><th>순위</th><th>종목명</th><th>티커</th><th>종가(원)</th><th>등락률</th><th>거래량</th><th>거래대금(원)</th><th>해석</th></tr>
        </thead>
        <tbody>
          {to_rows(losers)}
        </tbody>
      </table>
    </div>
  </section>

  <section class=\"panel\">
    <h2>해석 요약</h2>
    <ul class=\"policy-list\">
      <li>당일 등락률은 장마감 기준이며 실시간 변동과 다를 수 있습니다.</li>
      <li>상승/하락 종목은 시장 전체 흐름과 개별 이슈의 영향을 동시에 받습니다.</li>
      <li>본 자료는 투자 권유가 아닌 정보 제공용 요약입니다.</li>
    </ul>
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
    }


def build_index(reports: List[Dict[str, str]]) -> str:
    cards = []
    for r in sorted(reports, key=lambda x: x["date"], reverse=True):
        cards.append(
            f"""
<article class=\"report-card\">
  <h3><a href=\"/{r['path']}\">{r['date']} 주식장 분석</a></h3>
  <p>상승 대표: {r['strong']}</p>
  <p>하락 대표: {r['weak']}</p>
  <a class=\"read-link\" href=\"/{r['path']}\">하루치 상세 보기</a>
</article>
"""
        )

    body = f"""
<header class=\"site-header\">
  <div class=\"header-inner\">
    <a class=\"brand\" href=\"/\">{SITE_NAME}</a>
    <nav class=\"site-nav\" aria-label=\"주요 메뉴\">
      <a href=\"#reports\">최근 2주 리포트</a>
      <a href=\"/privacy.html\">개인정보처리방침</a>
      <a href=\"/terms.html\">이용약관</a>
    </nav>
  </div>
</header>

<main class=\"app\">
  <section class=\"hero\">
    <p class=\"kicker\">KOREA STOCK BLOG</p>
    <h1>매일 한국 주식 상승 30 / 하락 30 분석</h1>
    <p class=\"desc\">최근 2주(최근 10거래일) 장마감 데이터를 기준으로, 하루에 1페이지씩 요약 리포트를 제공합니다.</p>
    <p class=\"meta-line\">페이지 구성: 일자별 상승 30 · 하락 30 · 거래 집중도 · 해석 요약</p>
  </section>

  <section id=\"reports\" class=\"panel\">
    <h2>최근 2주 일자별 페이지</h2>
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


def main() -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    for old in REPORT_DIR.glob("*.html"):
        old.unlink()

    today = dt.date.today()
    start = today - dt.timedelta(days=20)
    biz_days = stock.get_previous_business_days(fromdate=start, todate=today)
    target_days = biz_days[-10:]

    reports: List[Dict[str, str]] = []

    for i, day in enumerate(target_days):
        prev_day = target_days[i - 1] if i > 0 else None
        next_day = target_days[i + 1] if i + 1 < len(target_days) else None
        report = build_day_report(day, i + 1, len(target_days), prev_day, next_day)
        (REPORT_DIR / f"{report['date']}.html").write_text(report["html"], encoding="utf-8")
        reports.append(report)

    INDEX_FILE.write_text(build_index(reports), encoding="utf-8")
    SITEMAP_FILE.write_text(build_sitemap([r["path"] for r in reports]), encoding="utf-8")

    print("generated", len(reports), "daily report pages")
    print("days", ", ".join(r["date"] for r in reports))


if __name__ == "__main__":
    main()
