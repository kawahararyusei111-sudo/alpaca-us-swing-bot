# Alpaca US株 ペーパートレードBot

Alpacaのペーパートレード口座（仮想資金、実資金は一切動かさない）で、米国株を
SMA(20/50)クロスオーバーのルールに従って自動売買するBot。GitHub Actionsの
定期実行で動くので、PCがスリープ/シャットダウンしていても稼働し続ける。

## 戦略ルール（`trade_bot.py`）

- 監視銘柄: AAPL, MSFT, SPY, QQQ, NVDA（固定・裁量判断なし）
- 1時間足でSMA20とSMA50を計算
  - ゴールデンクロス（SMA20がSMA50を上抜け）→ 未保有かつ保有銘柄数が3未満なら、資産の15%相当を買い
  - デッドクロス（SMA20がSMA50を下抜け）→ 保有していれば全量売り
  - 保有ポジションの含み損が-5%以下になったら、シグナルに関わらず即売り（損切り）
- 米国市場が閉まっている時間は何もせず終了（Alpacaの `/v2/clock` で判定、祝日も自動対応）

## セットアップ

1. [alpaca.markets](https://alpaca.markets) でアカウント作成 → **Paper Trading** の API Key ID / Secret Key を発行
2. このリポジトリの GitHub 上で **Settings → Secrets and variables → Actions → New repository secret** から以下を登録
   - `ALPACA_API_KEY_ID`
   - `ALPACA_API_SECRET_KEY`
3. `.github/workflows/trade.yml` が平日UTC 14,16,18,20時（米国市場が開いている時間帯を広めにカバー）に自動実行される
4. 手動で1回試したい場合は GitHub の **Actions** タブ → 「Alpaca paper trade」→ **Run workflow** で即実行できる

## 実行結果の確認

GitHub の **Actions** タブから各実行のログを確認できる。売買判断・注文結果はすべてログに出力される。

## 安全装置

- `trade_bot.py` の `PAPER_BASE` はAlpacaのペーパー取引エンドポイントに固定されている。ライブ（実資金）取引に切り替えるには、このURLを意図的に書き換える必要がある。
- 1銘柄あたりの投資上限は資産の15%、同時保有は最大3銘柄まで。
- 含み損-5%で強制損切り。

## 免責事項

これは学習目的のペーパートレード（仮想資金）Botであり、実資金による投資助言ではない。
実資金で運用する場合は、戦略の妥当性・リスクを十分に検証すること。
