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
* **Web API:** Minimal Web System (Python標準ライブラリ `HTTPServer` 等を使用し、講義要件に完全準拠)
  
## 📂 Repository Structure
* `/app`: メインのアプリケーションコード（WebAPI，IoT制御，AI推論など）
* `/notebooks`: データ分析や機械学習モデルの実験用Jupyter Notebook (作ってないしなくてもいい)
* `/docs`: 企画書，アーキテクチャ図，プレゼン資料
* `.devcontainer`: VS Code用のDocker環境設定ファイル
* `/scripts`: コンテナ起動用のシェルスクリプト (`start-container.sh`) が含まれるディレクトリ(使っていない)
* `/instructions`: 個人が作ったそれぞれの機能について説明書を入れるところ(いらないかもしれない)

## 🚀 Getting Started

1. **リポジトリのクローン**
   ```bash
   git clone git@github.com:riririnn/AdvSoftwereG5.git 
   cd AdvSoftwereG5
2. VS Code で開き、コンテナを起動する
VS Codeでプロジェクトのルートディレクトリを開くと、画面右下に「コンテナで再度開く (Reopen in Container)」というポップアップが表示されるのでクリックします。
(※表示されない場合は、`Ctrl + Shift + P `でコマンドパレットを開き、`Dev Containers: Reopen in Container `を選択してください)
3. 自動環境構築の完了を待つ
VS Codeが自動的に `docker/Dockerfile `を読み込み、Gitの導入、リポジトリルートの `/workspace `へのマウント、および依存パッケージの初期化（`update-dependencies.sh `の実行）を行います。完了すると、コンテナ内のターミナルでそのままGit管理やPythonの実行が可能になります。

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
   git commit -m "何をしたか(what do)，何に対してか(waht purpose)"
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
