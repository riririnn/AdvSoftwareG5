# 結合テストに向けた修正内容まとめ

全コード精査（app/ 全ファイル・Flask/ 主要部・theft_checker 883行を含む）で
発見した問題と、その修正内容の記録。2026-07-11 実施。

---

## 1. controller.py のダミー3関数をAI実装に差し替え

**問題**: `detect_person / detect_coin / detect_vegetables` がキーボード入力・固定値の
ダミーのままで、AIによる自動判定ができなかった。カメラからフレームを取得するコード
自体が存在しなかった。

**修正**:
- 3関数すべてを「カメラ取得 → GPUサーバー `/predict` → 形式変換」の実装に差し替え
- サーバーURL・信頼度しきい値を `config.py` に追加（`PREDICT_SERVER_URL` ほか）
- `python controller.py --dummy` で従来のキーボード式に切替可能（制御フロー単体テスト用）

**検証**: 実サーバー＋テスト画像で、硬貨5枚検出・野菜集計・人検知の全パターン確認済み。

### コインの重複カウント防止（設計上の追加対策）

コイン認識は0.2秒周期で呼ばれるため、トレイに置かれたままの硬貨を毎周期
記録すると `coin.csv` の合計金額が実際の何倍にもなってしまう。
**前回検出より増えた枚数だけを「新規投入」として返す差分方式**にし、
セッション開始時にリセットする（`reset_coin_tracking()`）。

### クラス混入の防止

- `detect_coin()`: 硬貨6種（1〜500円）のみ金額に変換。紙幣（1000yen等）・野菜・人は無視
- `detect_vegetables()`: 硬貨・紙幣・person を集計から除外

---

## 2. launcher.py の起動場所依存クラッシュ

**問題**: `subprocess.run(["python", "theft_checker.py", ...])` と相対パスで起動していた
ため、`app/` 以外のディレクトリから controller を実行すると**セッション終了時に必ず
クラッシュ**していた（`check=True` のため例外で停止）。

**修正**: `theft_checker.py` を絶対パス（`Path(__file__).parent / ...`）で指定し、
インタプリタも `sys.executable` に変更（`python` コマンドが無い環境でも動く）。

**検証**: リポジトリルートから `launch()` を実行し、万引き判定が完走することを確認
（正常購入シナリオ: 200円分減少・200円投入 → NORMAL判定）。

---

## 3. controllerとFlaskのセッションフォルダ不一致

**問題**: controller は `<リポジトリルート>/sessions/` に保存するが、Flask は
`Flask/sessions/` を監視していたため、**セッションが永遠に取り込まれなかった**
（在庫更新・売上記録・LINE通知がすべて動かない）。

**修正**: Flask の監視先デフォルトを controller の保存先に統一。
環境変数 `SESSIONS_DIR` での上書きは維持。

---

## 4. 重量センサーの負値で万引き判定がERRORになる

**問題**: theft_checker は weight.csv に負の値があると判定不能（ERROR）にする仕様。
空のコインボックスではセンサーノイズで -0.3g 等の負値が出るため、
**正常な状態でも判定がERRORになる**リスクがあった。

**修正**: `raspberry_pi.get_weights()` で負の計測値を 0.0 にクランプ。

---

## 5. 録画にフレームが書き込まれない

**問題**: controller は `recorder.start()/stop()` は呼ぶが `recorder.write(frame)` の
呼び出しが「Camera担当実装待ち」のコメントのみで、**monitor.mp4 が空**だった。

**修正**: セッション中のループで監視カメラのフレームを取得して録画に書き込む実装を追加。
同じフレームを人検知（`detect_person(frame)`）にも使い回し、カメラ読み出しを
1周1回に抑えた。

---

## 6. カメラ構成の変更（3台 → 2台）

**変更**: 監視カメラ=0、コイン・野菜カメラ=1（共用）に設定
（`app/config.py` の `VEGETABLE_CAMERA_INDEX = 1`）。

同じindexを指定するとcontroller内部で1つの `VideoCapture` を自動共有するため、
コードの変更は不要で設定値のみで台数を増減できる。

---

## 7. 重量センサー実装の統合（vegetable_weight_check.py → raspberry_pi.py）

**問題**: 重量担当がコミットした `vegetable_weight_check.py` は画面表示のみの
単体スクリプトで、controller が期待する `get_weights()` インターフェースと
接続されていなかった。

**修正**: HX711×2（コイン用・野菜用）のセンサーコードを `app/raspberry_pi.py` の
`get_weights()` に統合。

- ラズパイ実機では実測、PC等では自動でダミー値にフォールバック
- ゼロ点調整は起動時1回のみ（毎回行うと物が乗った状態が基準になるため）
- 野菜台の風袋（`TARE_VEGE_PLATFORM = 148.0`）を差し引き。**値は実測で要確認**
- `python app/raspberry_pi.py` で単体の計測確認が可能
- `Dockerfile.rpi` に `hx711` パッケージを追加

---

## 当日の残作業（コード外）

1. **`app/config.py` の `PREDICT_SERVER_URL` をGPUサーバーの実IPに書き換える**（これだけは必須）
2. 野菜台の風袋 `TARE_VEGE_PLATFORM` を実測で確認（重量担当）
3. LINE通知のトークン設定確認（Web UI担当）

テスト手順・成功条件は `docs/integration_test.md` を参照。
