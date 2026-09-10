"""Generate a static docs/index.html snapshot of the Alpaca paper account.

Runs after trade_bot.py in the GitHub Actions workflow. The output is a
plain HTML file with no client-side API calls, so it can be served
publicly via GitHub Pages without ever exposing the Alpaca API keys.
"""
import html
import json
import os
import urllib.error
import urllib.request
from datetime import datetime, timezone

PAPER_BASE = "https://paper-api.alpaca.markets"


def _headers():
    return {
        "APCA-API-KEY-ID": os.environ["ALPACA_API_KEY_ID"],
        "APCA-API-SECRET-KEY": os.environ["ALPACA_API_SECRET_KEY"],
    }


def req(path):
    r = urllib.request.Request(f"{PAPER_BASE}{path}", headers=_headers())
    with urllib.request.urlopen(r, timeout=20) as resp:
        return json.loads(resp.read())


def esc(v):
    return html.escape(str(v))


def render(account, positions, orders):
    equity = float(account["equity"])
    last_equity = float(account["last_equity"])
    day_pl = equity - last_equity
    day_pl_pct = (day_pl / last_equity * 100) if last_equity else 0
    updated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    pos_rows = ""
    for p in positions:
        pl = float(p["unrealized_pl"])
        pl_pct = float(p["unrealized_plpc"]) * 100
        cls = "pos" if pl >= 0 else "neg"
        pos_rows += f"""<tr>
          <td>{esc(p['symbol'])}</td>
          <td>{esc(p['qty'])}</td>
          <td>${float(p['avg_entry_price']):.2f}</td>
          <td>${float(p['current_price']):.2f}</td>
          <td>${float(p['market_value']):.2f}</td>
          <td class="{cls}">{pl:+.2f} ({pl_pct:+.2f}%)</td>
        </tr>"""
    if not pos_rows:
        pos_rows = '<tr><td colspan="6" class="empty">保有中の銘柄はありません</td></tr>'

    order_rows = ""
    for o in orders[:20]:
        filled_price = o.get("filled_avg_price")
        price_str = f"${float(filled_price):.2f}" if filled_price else "-"
        order_rows += f"""<tr>
          <td>{esc(o.get('filled_at') or o.get('submitted_at') or '')[:19].replace('T', ' ')}</td>
          <td>{esc(o['symbol'])}</td>
          <td>{esc(o['side'])}</td>
          <td>{esc(o.get('qty') or o.get('notional') or '')}</td>
          <td>{price_str}</td>
          <td>{esc(o['status'])}</td>
        </tr>"""
    if not order_rows:
        order_rows = '<tr><td colspan="6" class="empty">注文履歴はまだありません</td></tr>'

    day_cls = "pos" if day_pl >= 0 else "neg"

    return f"""<!doctype html>
<html lang="ja"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Alpaca US株 スイングBot</title>
<style>
  :root {{ color-scheme: light dark; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; max-width: 900px; margin: 2rem auto; padding: 0 1rem; background: #fafafa; color: #1a1a1a; }}
  @media (prefers-color-scheme: dark) {{ body {{ background: #111; color: #eee; }} table {{ background: #1c1c1c; }} th {{ background: #222 !important; }} td {{ border-color: #333 !important; }} .card {{ background: #1c1c1c !important; }} }}
  h1 {{ font-size: 1.4rem; }}
  .updated {{ color: #888; font-size: 0.85rem; margin-bottom: 1.5rem; }}
  .cards {{ display: flex; gap: 1rem; flex-wrap: wrap; margin-bottom: 2rem; }}
  .card {{ background: #fff; border-radius: 10px; padding: 1rem 1.5rem; box-shadow: 0 1px 3px rgba(0,0,0,0.1); flex: 1; min-width: 140px; }}
  .card .label {{ font-size: 0.8rem; color: #888; }}
  .card .value {{ font-size: 1.3rem; font-weight: 600; }}
  table {{ width: 100%; border-collapse: collapse; margin-bottom: 2rem; font-size: 0.9rem; }}
  th, td {{ text-align: left; padding: 0.5rem 0.6rem; border-bottom: 1px solid #eee; }}
  th {{ background: #f0f0f0; font-weight: 600; }}
  .pos {{ color: #0a7d2c; }}
  .neg {{ color: #c0392b; }}
  .empty {{ color: #999; text-align: center; }}
</style>
</head><body>
<h1>Alpaca US株 スイングBot ダッシュボード</h1>
<div class="updated">最終更新: {updated}（数時間おきに自動更新）</div>

<div class="cards">
  <div class="card"><div class="label">評価額 (Equity)</div><div class="value">${equity:,.2f}</div></div>
  <div class="card"><div class="label">現金 (Cash)</div><div class="value">${float(account['cash']):,.2f}</div></div>
  <div class="card"><div class="label">本日の損益</div><div class="value {day_cls}">{day_pl:+.2f} ({day_pl_pct:+.2f}%)</div></div>
</div>

<h2>保有ポジション</h2>
<table>
  <tr><th>銘柄</th><th>数量</th><th>取得単価</th><th>現在値</th><th>評価額</th><th>含み損益</th></tr>
  {pos_rows}
</table>

<h2>直近の注文履歴</h2>
<table>
  <tr><th>日時</th><th>銘柄</th><th>売買</th><th>数量</th><th>約定価格</th><th>状態</th></tr>
  {order_rows}
</table>

<p style="color:#888; font-size:0.85rem;">これは<b>ペーパートレード（仮想資金）</b>の記録です。実資金は一切使用していません。戦略ルールは <a href="https://github.com/kawahararyusei111-sudo/alpaca-us-swing-bot">GitHubリポジトリ</a> のREADMEを参照。</p>
</body></html>"""


def main():
    account = req("/v2/account")
    positions = req("/v2/positions")
    orders = req("/v2/orders?status=all&limit=20&direction=desc")

    os.makedirs("docs", exist_ok=True)
    with open("docs/index.html", "w", encoding="utf-8") as f:
        f.write(render(account, positions, orders))
    print("docs/index.html を更新しました")


if __name__ == "__main__":
    main()
