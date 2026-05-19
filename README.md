# Advanced Software Engineering - Team Project

応用ソフトウェア工学のPBL（プロジェクトベース学習）におけるチーム開発用リポジトリです．

## 🎯 Project Goal
- 無人販売におけるお金の支払い問題を手助けするシステムを構築します．
- Raspberry PiのGPIO・SPI通信を用いたセンサー制御（磁気・重量）と，カメラを用いたAI画像認識（お金の枚数計算・野菜のラベリング分類）を組み合わせ，購入や万引きの認識と外部への通知を自動化します．

## 🛠 Tech Stack & Environment
* **Language:** Python 3.9
* **Environment:** Ubuntu (WSL) / Docker (Dev Containers)
* **Target Area:** IoT / AI
* **Infrastructure:** Local Raspberry Pi (OS Lite 32bit / Debian Bullseyeベース)
  
## 📂 Repository Structure
* `/app`: メインのアプリケーションコード（WebAPI，IoT制御，AI推論など）
* `/notebooks`: データ分析や機械学習モデルの実験用Jupyter Notebook
* `/docs`: 企画書，アーキテクチャ図，プレゼン資料
* `.devcontainer`: VS Code用のDocker環境設定ファイル
* `/docker`: 環境構築用の `Dockerfile` が含まれるディレクトリ
* `/scripts`: コンテナ起動用のシェルスクリプト (`start-container.sh`) が含まれるディレクトリ

## 🚀 Getting Started

1. **リポジトリのクローン**
   ```bash
   git clone git@github.com:riririnn/AdvSoftwereG5.git 
   cd AdvSoftwereG5
2. Dockerイメージのビルド
   `docker/Dockerfile` には，GPIO・カメラ操作に必要な依存パッケージ（`libi2c-dev, v4l-utils`）と，AI推論用の軽量ライブラリ（`tflite-runtime, opencv-python-headless`）が含まれています．
   以下のコマンドで，スクリプトに指定されている名前（`advsoftwareg5:latest`）でイメージをビルドします．
   ```
   docker build -t advsoftwareg5:latest -f docker/Dockerfile .
   ```
3. コンテナの起動
   `scripts/start-container.sh`を使用してコンテナを起動します．
   このスクリプトは，既存の`advsoftwareg5`コンテナが存在する場合は自動的に停止・削除し，ハードウェアデバイスへのアクセス権限（GPIO: `/dev/gpiomem`, SPI: `/dev/spidev0.0`, `/dev/spidev0.1`, カメラ: `/dev/video0`）を付与して起動します．
   ```
   # 実行権限の付与（初回のみ）
   chmod +x scripts/start-container.sh
   # スクリプトの実行
   ./scripts/start-container.sh
   ```

## 💻 Development (チーム開発の進め方)

本プロジェクトでは，ハードウェア（Raspberry Pi）とソフトウェア（AI/Web）の開発を効率よく進めるため，「手元のPCで開発 ➔ GitHubで共有 ➔ ラズパイで実機テスト」 というフローを採用しています．

### Step 1: 手元のPC（WSL）でのコード実装

各メンバーは，基本的に自身のPC上でコード（PythonスクリプトやDockerfile等）の編集を行います．

1. 最新のコードを取得する

   作業を始める前に，必ずリモートの最新状態を反映させます．

   ```bash
   git pull origin main
   ```

2. 作業用ブランチを作成する

   直接 `main` ブランチを編集せず，機能ごとにブランチを切って作業します（例: カメラ機能の実装）．

   ```bash
   git checkout -b feature/camera-recognition
   ```

3. VS Code + Dev Containers で開発する（ガチで推奨）

   VS Codeでフォルダを開き，右下のポップアップまたはコマンドパレットから Reopen in Container を選択します．これにより，コンテナ内のPython環境がVS Codeに認識され，構文エラーのチェックや自動補完が効くようになります．

   ⚠️ 注意: 手元のPCにはセンサーやカメラが繋がっていないため，ハードウェア依存のコードをテストする際はダミーデータを用意するか，実機テストで行います．

### Step 2-1: GitHub への共有（ブランチ内でのコード管理）

誰かとブランチを共有して開発を行っている場合はこまめにcommit，push，pullを行い，開発状況を共有してください．

またコンフリクトが極力起きないように同じ個所を同時に編集しないように心がけてください(編集する場合は本当にこまめにプッシュを行うように)

※VScode上の拡張機能で管理することをおすすめします．

1. 変更をコミットしてプッシュする ( local → remote )

   ```
   (originリポジトリのfeature/camera-recognitionブランチの場合)
   git add .
   git commit -m "カメラの画像認識処理の基本ロジックを追加"
   git push origin feature/camera-recognition
   ```

2. ほかの人の変更を自分のコードに適用する( remote → local )

   ```
   (おすすめ)git pull --rebase
   もしくは git pull 
   ```

### Step 2-2: GitHub 上で作業ブランチを `main` へ統合する（Webで行う場合）

この動作は作業ブランチでの編集がすべて完了し，機能が完成した場合などに行ってください．

PCでプッシュした作業ブランチのコードを，プロジェクトの正規コード（`main` ブランチ）へと統合します．この作業は GitHubのウェブ画面で行います．

1. GitHubのリポジトリ画面を開く

   ブラウザでGitHubにアクセスすると，画面上部に「feature/camera-fix had recent pushes...」という黄色いバーが表示されるので，その横にある [Compare & pull request] ボタンを押します．

2. Pull Request (PR) を作成する

   変更内容のタイトルやメモを記入し，画面右下の [Create pull request] ボタンを押します．

3. コードを統合（マージ）する

   画面が切り替わり，自動で競合（コンフリクト）のチェックが行われます．問題がなければ，緑色の [Merge pull request] ➔ [Confirm merge] の順にボタンを押します．

   これで，あなたの書いた修正コードがGitHub上の `main` ブランチへ正式に統合されました．

### Step 3: Raspberry Pi 実機でのデプロイとテスト

センサーやカメラを使った実際の動作確認は，Raspberry Pi本体で行います．

1. Raspberry Piで最新コードを取得する

   ラズパイのターミナルを開き，マージされた最新のコードを引っ張ってきます．

   ```bash
   git checkout main
   git pull origin main
   ```

2. ラズパイ上でDockerイメージをビルドする

   ラズパイ上で以下のコマンドを実行し，Raspberry Pi（ARM）用のコンテナを構築します．

   ```bash
   docker build -t advsoftwareg5:latest -f docker/Dockerfile .
   ```

3. コンテナを起動する

   起動スクリプトを実行し，コンテナを起動します．

   ```bash
   ./scripts/start-container.sh
   ```

4. ログを確認してデバッグする

   エラーが起きていないか，リアルタイムログで確認します．

   ```bash
   docker logs -f advsoftwareg5_app
   ```

### 🔁 デバッグサイクルについて

実機テストでエラー（バグ）が見つかった場合は，「ラズパイ上で直接コードを直す」ことは極力避け，以下のサイクルを回してください．

1. エラー内容（ログ）をメモする．
2. 手元のPC（WSL） に戻り，VS Codeでコードを修正する．
3. 再度 GitHub に Push する．
4. ラズパイで Pull し，スクリプトを実行して再起動・確認する．
