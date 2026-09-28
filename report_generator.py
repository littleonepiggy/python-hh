"""Build an HTML report from vacancies.json and open it in Firefox.

Vacancies are listed best-first (sorted by the AI analysis score).
Each card links to the vacancy page on hh.ru.
"""

import html
import json
import shutil
import subprocess
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent
REPORT_PATH = PROJECT_DIR / "index.html"
VACANCIES_PATH = PROJECT_DIR / "vacancies.json"


def _score_sort_key(vacancy: dict) -> float:
    """Sort key by analysis score; entries without a score sink to the end."""
    raw = (vacancy.get("analysis") or {}).get("score")
    try:
        return float(str(raw).rstrip("%"))
    except (TypeError, ValueError, AttributeError):
        return -1.0


def _esc(value) -> str:
    """HTML-escape any value for safe embedding."""
    return html.escape(str(value if value is not None else ""))


def _score_class(score: float) -> str:
    """CSS class for the score badge color."""
    if score >= 80:
        return "good"
    if score >= 60:
        return "mid"
    return "low"


def _render_card(entry: dict) -> str:
    """Render one vacancy card as HTML."""
    analysis = entry.get("analysis") or {}

    try:
        score = float(str(analysis.get("score", "")).rstrip("%"))
    except (TypeError, ValueError):
        score = -1.0

    title = entry.get("title") or "(untitled vacancy)"
    company = entry.get("company") or ""
    link = entry.get("link", "#")
    salary = analysis.get("salary")
    fmt = analysis.get("format")
    stack = analysis.get("stack") or []
    rel = analysis.get("rel")
    pros = analysis.get("pros") or []
    cons = analysis.get("cons") or []
    letter = analysis.get("letter")

    if score < 0:
        badge = '<div class="score none">—</div>'
    else:
        badge = f'<div class="score {_score_class(score)}">{int(score)}%</div>'

    parts = [f'<div class="card">']
    parts.append(badge)
    parts.append('<div class="body">')
    parts.append(f'<a class="title" href="{_esc(link)}" target="_blank">{_esc(title)}</a>')
    parts.append('<div class="meta">')
    if company:
        parts.append(f'<span class="company">{_esc(company)}</span>')
    if fmt:
        parts.append(f'<span class="chip">{_esc(fmt)}</span>')
    if salary:
        parts.append(f'<span class="chip salary">{_esc(salary)}</span>')
    parts.append("</div>")
    if rel:
        parts.append(f'<div class="rel">{_esc(rel)}</div>')
    if stack:
        chips = "".join(f'<span class="stack-chip">{_esc(s)}</span>' for s in stack)
        parts.append(f'<div class="stack">{chips}</div>')

    details_inner = ""
    if pros:
        items = "".join(f"<li>{_esc(p)}</li>" for p in pros)
        details_inner += f'<div class="col pros"><h4>✅ Плюсы</h4><ul>{items}</ul></div>'
    if cons:
        items = "".join(f"<li>{_esc(c)}</li>" for c in cons)
        details_inner += f'<div class="col cons"><h4>❌ Минусы</h4><ul>{items}</ul></div>'
    if letter:
        details_inner += f'<div class="letter">✉️ {_esc(letter)}</div>'
    if details_inner:
        parts.append(
            f'<details><summary>Подробнее</summary><div class="details">{details_inner}</div></details>'
        )
    parts.append("</div></div>")
    return "\n".join(parts)


def generate_report(vacancies: list[dict], report_path: Path = REPORT_PATH) -> Path:
    """Write the HTML report file and return its path."""
    vacancies = sorted(vacancies, key=_score_sort_key, reverse=True)
    cards = "\n".join(_render_card(v) for v in vacancies)

    page = f"""<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="utf-8">
<title>HH вакансии — по релевантности</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
         background: #f4f5f7; color: #222; padding: 24px; }}
  h1 {{ font-size: 22px; margin-bottom: 4px; }}
  .sub {{ color: #777; font-size: 13px; margin-bottom: 20px; }}
  .card {{ display: flex; gap: 16px; background: #fff; border: 1px solid #e2e4e8;
          border-radius: 10px; padding: 16px; margin-bottom: 12px;
          box-shadow: 0 1px 2px rgba(0,0,0,.04); }}
  .score {{ flex: 0 0 64px; height: 64px; border-radius: 10px; display: flex;
           align-items: center; justify-content: center;
           font-size: 18px; font-weight: 700; color: #fff; }}
  .score.good {{ background: #2e9e5b; }}
  .score.mid  {{ background: #e0a52e; }}
  .score.low  {{ background: #d05454; }}
  .score.none {{ background: #aaa; }}
  .body {{ flex: 1; min-width: 0; }}
  .title {{ font-size: 17px; font-weight: 600; color: #1a5dab;
           text-decoration: none; word-break: break-word; }}
  .title:hover {{ text-decoration: underline; }}
  .meta {{ display: flex; flex-wrap: wrap; gap: 8px; align-items: center;
          margin: 6px 0; font-size: 13px; }}
  .company {{ font-weight: 600; }}
  .chip {{ background: #eef1f4; border-radius: 12px; padding: 2px 10px; }}
  .chip.salary {{ color: #2e7d32; font-weight: 600; }}
  .rel {{ font-size: 13.5px; color: #555; margin: 6px 0; }}
  .stack {{ display: flex; flex-wrap: wrap; gap: 6px; margin: 6px 0; }}
  .stack-chip {{ background: #e8f0fe; color: #1a5dab; font-size: 12px;
                border-radius: 10px; padding: 2px 8px; }}
  details {{ margin-top: 8px; font-size: 13.5px; }}
  summary {{ cursor: pointer; color: #1a5dab; }}
  .details {{ display: flex; gap: 24px; flex-wrap: wrap; margin-top: 8px; }}
  .col ul {{ margin-left: 18px; }}
  .col li {{ margin-bottom: 3px; }}
  .col h4 {{ font-size: 13px; margin-bottom: 4px; }}
  .letter {{ flex-basis: 100%; background: #f8f6ef; border-radius: 8px;
            padding: 10px; font-size: 13px; }}
</style>
</head>
<body>
<h1>🕸️ HH вакансии — анализ</h1>
<div class="sub">Отсортировано по релевантности: лучшие сверху. Нажмите на название, чтобы открыть вакансию.</div>
{cards}
</body>
</html>
"""

    report_path.write_text(page, encoding="utf-8")
    return report_path


def open_in_firefox(report_path: Path) -> None:
    """Open the report in Firefox (non-blocking)."""
    firefox = shutil.which("firefox")
    if firefox:
        subprocess.Popen([firefox, "--new-window", report_path.as_uri()])
    else:
        import webbrowser
        webbrowser.open(report_path.as_uri())


def generate_and_open_report(vacancies: list[dict] | None = None) -> Path | None:
    """Generate index.html and open it in Firefox.

    Args:
        vacancies: list to render. If None, loads vacancies.json.
    """
    if vacancies is None:
        if not VACANCIES_PATH.exists():
            print("  ⚠️  No vacancies.json — nothing to report.")
            return None
        with open(VACANCIES_PATH, "r", encoding="utf-8") as f:
            vacancies = json.load(f)

    if not vacancies:
        print("  ⚠️  No vacancies collected — nothing to report.")
        return None

    vacancies = sorted(vacancies, key=_score_sort_key, reverse=True)
    report_path = generate_report(vacancies)
    print(f"  📄 Report saved: {report_path}")

    open_in_firefox(report_path)
    print("  🌐 Opened in Firefox.")
    return report_path


if __name__ == "__main__":
    generate_and_open_report()
