# Web管理画面

無人販売支援システムのWeb管理画面です。

## 配置

```text
app/web_admin/
├─ web_app.py
├─ data_store.py
├─ line_notify.py
├─ templates/
└─ static/
```

古い `Flask/` フォルダは使用しません。

## 起動方法

リポジトリ直下で実行します。

```bash
pip install -r requirements.txt
python -m app.web_admin.web_app
```

## 実行時データ

以下はGit管理せず、実行時に生成します。

```text
runtime/data_store.json
runtime/processed_sessions.json
sessions/
```

Web管理画面で登録した商品情報・重量センサー設定は、制御側と共通の `app/config.py` に反映されます。
