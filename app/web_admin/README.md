# Web管理画面（Flask）

このディレクトリは、無人販売支援システムのWeb管理画面です。

## 役割

- 商品登録
- 在庫表示・在庫変更
- 重量センサー設定
- session.json 取込
- 売上履歴・通知履歴表示
- LINE購入通知・万引き通知
- 万引き時の動画通知

## 起動方法

リポジトリ直下で実行してください。

```bash
python -m app.web_admin.web_app
```

または、直接実行する場合は以下です。

```bash
python app/web_admin/web_app.py
```

## 保存先

- セッション: `sessions/`
- Webデータ: `runtime/data_store.json`
- 処理済みsession記録: `runtime/processed_sessions.json`
- Webが更新する設定: `app/config.py`

## 注意

`runtime/` と `sessions/` は実行時データなので、Gitには入れません。
