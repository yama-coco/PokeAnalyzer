# ソフトウェア仕様書・詳細設計書: PokeAnalysis Live for Champions (PAL-C)

## 1. プロジェクト概要

本作は『ポケモンチャンピオンズ』(Switch 2) のダブルバトル（レギュレーション M-A準拠）における対戦データの自動収集・リアルタイム分析ツールである。OBS Studioからの映像ソースを基に、画像認識(CV)とOCRを用いて、相手の選出、行動、ダメージ、素早さ関係を可視化し、プレイヤーの意思決定を支援する。

---

## 2. システム要件

### 2.1 機能要件

1.  **パーティ登録管理:** - 自パーティ（6体）の種族、特性、持ち物、技、実数値、テラスタイプ、メガシンカの有無を登録。
2.  **リアルタイム映像解析 (Vision Engine):**
    - **VS画面検知:** 相手の6体のアイコンを識別し、Game8等の外部データから想定される型を提示。
    - **選出特定:** バトル開始時の繰り出し順（先発2体・後発2体）を自動記録。
    - **行動ログ:** テキストボックスから技名、特性、持ち物、メガシンカ、テラスタルの発動をOCRで抽出。
    - **ダメージ計算:** HPバーの減少率から相手の耐久調整（EVs）を逆算。
3.  **ダブルバトル特化分析:**
    - **素早さ順(Speed Tier)表示:** 天候、追い風、トリル、スカーフ等を加味した場に出ている4体の行動順を常時表示。
    - **まもる管理:** 相手の「まもる」使用状況と連続成功確率の表示。
4.  **OBS連携:**
    - OBS WebSocket 5.x を使用し、対戦開始・終了に合わせて自動録画やシーン切替を実行。
    - ブラウザソースとして解析結果をOBS上にオーバーレイ表示。

### 2.2 非機能要件

- **低遅延:** 映像の変化から1秒以内に解析結果を画面に反映すること。
- **高精度:** 最新のUIに対応した画像認識モデル（YOLOv10等）を使用すること。

---

## 3. 技術スタック

- **Backend:** Python 3.10+, FastAPI, uvicorn
- **Vision:** OpenCV, PyTorch (YOLOv10), PaddleOCR
- **Frontend:** React 19, TypeScript, Tailwind CSS v4, Vite
- **Database:** SQLite (SQLAlchemy)
- **Integration:** OBS WebSocket 5.x, WebSockets
- **パッケージ管理:** uv (Backend), npm (Frontend)

---

## 4. ローカル環境セットアップ

### 4.1 前提条件

| ツール     | バージョン | 用途                  |
| ---------- | ---------- | --------------------- |
| Python     | 3.10+      | バックエンド          |
| Node.js    | 18+        | フロントエンド        |
| uv         | 最新       | Python パッケージ管理 |
| OBS Studio | 30+ (任意) | 映像キャプチャ連携    |

### 4.2 バックエンドセットアップ

```bash
cd backend

# 依存関係インストール
uv sync

# (任意) Vision Engine の追加依存 (PaddleOCR, YOLO)
uv sync --extra vision

# (任意) 開発ツール (pytest, ruff, httpx)
uv sync --extra dev

# サーバー起動
uv run uvicorn app.main:app --reload --port 8000
```

起動後:

- **Swagger UI (API ドキュメント):** http://localhost:8000/docs
- **ReDoc:** http://localhost:8000/redoc

### 4.3 フロントエンドセットアップ

```bash
cd frontend

# 依存関係インストール
npm install

# 開発サーバー起動
npm run dev
```

起動後:

- **フロントエンド:** http://localhost:5173
- Vite プロキシにより `/api/*` リクエストは自動的に `localhost:8000` へ転送される

### 4.4 テスト実行

```bash
# バックエンドテスト (248テスト)
cd backend
uv run pytest

# 詳細出力
uv run pytest -v

# 特定テストファイル
uv run pytest tests/test_speed_calculator.py

# Lint チェック
uv run ruff check app/ tests/

# フロントエンド型チェック
cd frontend
npx tsc --noEmit

# フロントエンドビルド
npm run build
```

### 4.5 OBS Studio 連携 (任意)

OBS Studio で映像解析を行う場合:

1. OBS Studio で **WebSocket サーバー** を有効化:
   - `ツール` → `WebSocket サーバー設定` → `WebSocketサーバーを有効にする` にチェック
   - ポート: `4455` (デフォルト)
2. **仮想カメラ** を開始 (`ツール` → `仮想カメラ開始`)
3. PAL-C バックエンドから接続:
   ```
   POST http://localhost:8000/api/obs/connect
   ```

### 4.6 デスクトップアプリ (Electron)

PAL-C はブラウザ上での利用に加え、Electron によるスタンドアロンのデスクトップアプリケーションとしても利用可能です。デスクトップアプリでは起動時にバックエンドサーバーが自動起動されるため、手動でサーバーを立ち上げる必要がありません。

#### 4.6.1 前提条件

| ツール | バージョン | 用途 |
| ------ | ---------- | ---- |
| Node.js | 18+ | Electron / React ビルド |
| Python | 3.10+ | バックエンド (子プロセスとして自動起動) |
| uv | 最新 | Python パッケージ管理 (バックエンド起動に必要) |

> **注意:** Electron アプリ起動時にバックエンドが子プロセスとして `uv run uvicorn` で起動されるため、`uv` コマンドがシステム PATH に存在する必要があります。

#### 4.6.2 開発モード

開発中は Hot Module Replacement (HMR) が有効な状態で Electron ウィンドウが起動します。

```bash
cd frontend

# 依存関係インストール (初回のみ)
npm install

# Electron 用 TypeScript をビルド
npm run electron:build

# 開発モードで起動 (Vite + Electron 同時起動)
npm run electron:dev
```

**動作の流れ:**
1. Vite 開発サーバーが `http://localhost:5173` で起動
2. `wait-on` が Vite の起動を待機
3. バックエンドが子プロセスとして `localhost:8000` で自動起動
4. Electron ウィンドウが開き、Vite dev server を読み込み
5. DevTools が自動で開く (開発モードのみ)

**ソースコードを変更すると:**
- フロントエンド (React): HMR により即座に反映
- Electron メインプロセス (`electron/main.ts`): `npm run electron:build` を再実行後、アプリを再起動

#### 4.6.3 プレビューモード (本番ビルド確認)

本番環境と同じビルド成果物を Electron で表示して確認します。

```bash
cd frontend

# React アプリをビルド + Electron TypeScript をビルド + Electron で起動
npm run electron:preview
```

**動作の流れ:**
1. `npm run build`: Vite が React アプリを `dist/` にビルド (ELECTRON=true で相対パス)
2. `npm run electron:build`: TypeScript が `electron/` を `dist-electron/` にコンパイル
3. Electron が `dist/index.html` を `file://` プロトコルで読み込み
4. バックエンドが子プロセスとして自動起動

#### 4.6.4 配布パッケージのビルド

各プラットフォーム向けのインストーラーを生成します。

```bash
cd frontend

# 全プラットフォーム向けビルド (実行中の OS 向けが生成される)
npm run dist

# Windows 向け (.exe / NSIS インストーラー)
npm run dist:win

# macOS 向け (.dmg)
npm run dist:mac

# Linux 向け (.AppImage)
npm run dist:linux
```

**ビルド成果物:** `frontend/release/` ディレクトリに出力されます。

| プラットフォーム | 形式 | 出力例 |
| ---------------- | ---- | ------ |
| Windows | NSIS | `release/PAL-C Setup x.x.x.exe` |
| macOS | DMG | `release/PAL-C-x.x.x.dmg` |
| Linux | AppImage | `release/PAL-C-x.x.x.AppImage` |

> **注意:** クロスプラットフォームビルドには制限があります。Windows 向けは Windows 上で、macOS 向けは macOS 上でビルドすることを推奨します。

#### 4.6.5 パッケージ構成

配布パッケージには以下が含まれます:

```
PAL-C/
├── dist/              # ビルド済みフロントエンド (HTML/CSS/JS)
├── dist-electron/     # コンパイル済み Electron コード
│   ├── main.js        # メインプロセス
│   └── preload.js     # プリロードスクリプト
└── resources/
    └── backend/       # バックエンドコード (extraResources)
        ├── app/       # FastAPI アプリケーション
        ├── models/    # 学習モデル
        ├── data/      # データファイル
        └── pyproject.toml
```

#### 4.6.6 アーキテクチャ

```
┌─────────────────────────────────────────────────┐
│                 Electron Main Process            │
│  (frontend/electron/main.ts → dist-electron/)   │
├─────────────────────────────────────────────────┤
│                                                 │
│  ┌───────────────┐    ┌───────────────────────┐ │
│  │ BrowserWindow │    │ Backend (子プロセス)   │ │
│  │  (Renderer)   │◄──►│ uvicorn :8000         │ │
│  │  React App    │    │ FastAPI + Vision      │ │
│  └───────────────┘    └───────────────────────┘ │
│         │                                       │
│         │ contextBridge (preload.ts)            │
│         │  - platform: string                   │
│         │  - isElectron: boolean                │
│                                                 │
└─────────────────────────────────────────────────┘
```

**セキュリティ:**
- `nodeIntegration: false` — レンダラープロセスから Node.js API へのアクセスを遮断
- `contextIsolation: true` — メインプロセスとレンダラーのコンテキストを分離
- `contextBridge` — 必要最小限の API のみをレンダラーに公開

#### 4.6.7 トラブルシューティング

| 問題 | 原因 | 解決方法 |
| ---- | ---- | -------- |
| `uv: command not found` | uv が PATH にない | `curl -LsSf https://astral.sh/uv/install.sh \| sh` でインストール |
| バックエンドが起動しない | Python 依存関係未インストール | `cd backend && uv sync` を実行 |
| 画面が白いまま | Vite dev server 未起動 (開発モード) | `npm run electron:dev` を使用する |
| `ELECTRON=true` が効かない | 環境変数が渡されていない | `npm run build` 内で自動設定済み。手動ビルド時は `ELECTRON=true npx vite build` |
| ウィンドウが開かない | Electron バイナリ未ダウンロード | `npm install` を再実行 |
| ビルドに失敗する | 依存関係の問題 | `rm -rf node_modules && npm install` |
| macOS で「開発元を確認できない」| コード署名なし | `システム設定` → `セキュリティ` → `このまま開く` |

#### 4.6.8 npm スクリプト一覧

| スクリプト | 説明 |
| ---------- | ---- |
| `npm run electron:build` | Electron TypeScript を `dist-electron/` にコンパイル |
| `npm run electron:dev` | 開発モード起動 (Vite + Electron 並行) |
| `npm run electron:preview` | 本番ビルドを Electron で確認 |
| `npm run dist` | 配布パッケージ作成 (現在のOS向け) |
| `npm run dist:win` | Windows 向けパッケージ作成 |
| `npm run dist:mac` | macOS 向けパッケージ作成 |
| `npm run dist:linux` | Linux 向けパッケージ作成 |

---

### 4.7 ディレクトリ構成

```
PokeAnalyzer/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI アプリケーション
│   │   ├── database.py          # SQLAlchemy + SQLite 設定
│   │   ├── models.py            # DB モデル (my_parties, match_history, action_logs)
│   │   ├── schemas.py           # Pydantic スキーマ
│   │   ├── routers/
│   │   │   ├── party.py         # パーティ CRUD API
│   │   │   ├── battle.py        # バトル・素早さ・HP・ダメージ・まもる・ターンログ API
│   │   │   ├── obs.py           # OBS WebSocket 連携 API
│   │   │   └── vision.py        # Vision Engine 制御 API
│   │   └── services/
│   │       ├── speed_calculator.py    # 素早さ計算エンジン
│   │       ├── damage_calculator.py   # ダメージ計算 (第9世代準拠)
│   │       ├── hp_tracker.py          # HP 追跡 (OCR/パーセンテージ/バー解析)
│   │       ├── protect_manager.py     # まもる使用管理
│   │       ├── battle_state.py        # 試合状態管理
│   │       ├── turn_logger.py         # ターンアクション記録
│   │       ├── vision_engine.py       # 映像解析パイプライン
│   │       ├── scene_state.py         # シーンステートマシン
│   │       ├── frame_processor.py     # フレーム前処理・ROI 抽出
│   │       ├── template_matcher.py    # テンプレートマッチング
│   │       ├── ocr_engine.py          # PaddleOCR テキスト抽出
│   │       ├── yolo_detector.py       # YOLOv10 検出基盤
│   │       └── obs_connector.py       # OBS WebSocket クライアント
│   ├── tests/                   # 416 テスト
│   └── pyproject.toml
├── frontend/
│   ├── electron/
│   │   ├── main.ts              # Electron メインプロセス
│   │   └── preload.ts           # contextBridge プリロード
│   ├── src/
│   │   ├── pages/               # 8 ページコンポーネント
│   │   ├── api/                 # API クライアント
│   │   ├── components/          # 共通コンポーネント
│   │   └── types/               # TypeScript 型定義
│   ├── electron-builder.yml     # 配布パッケージビルド設定
│   ├── tsconfig.electron.json   # Electron 用 TypeScript 設定
│   ├── package.json
│   └── vite.config.ts
└── README.md
```

---

## 5. 実装済み機能一覧

### 5.1 バックエンド API (45+ エンドポイント)

#### パーティ管理 (`/api/parties/`)

| メソッド | パス                | 概要             |
| -------- | ------------------- | ---------------- |
| GET      | `/api/parties/`     | パーティ一覧取得 |
| POST     | `/api/parties/`     | パーティ新規作成 |
| GET      | `/api/parties/{id}` | パーティ詳細取得 |
| PUT      | `/api/parties/{id}` | パーティ更新     |
| DELETE   | `/api/parties/{id}` | パーティ削除     |

登録項目: 種族 (species)、特性 (ability)、持ち物 (item)、技 (moves)、実数値 (stats: HP/A/B/C/D/S)、テラスタイプ (tera_type)、メガシンカ可否 (can_mega_evolve)

#### 素早さ計算 (`/api/battle/speed-tiers`)

| 対応補正   | 詳細                                                      |
| ---------- | --------------------------------------------------------- |
| フィールド | 追い風 (×2)、トリックルーム (行動順反転)                  |
| 天候特性   | すいすい/ようりょくそ/すなかき/ゆきかき (天候時 ×2)       |
| アイテム   | こだわりスカーフ (×1.5)、くろいてっきゅう (×0.5)          |
| 特性       | はやあし (まひ無効)、かるわざ (×2)、スロースタート (×0.5) |
| 状態       | まひ (×0.5)、ランク変化 (-6〜+6)                          |

#### ダメージ計算 (`/api/battle/damage`)

第9世代準拠の計算式:

```
Damage = floor(floor(((2*Level/5+2) * Power * A/D) / 50 + 2) * Modifier * random / 100)
```

- 乱数幅: 85〜100 の16パターン
- STAB (タイプ一致 ×1.5)、範囲技補正 (×0.75)、タイプ相性 (0.25x〜4x)
- テラスタル・メガシンカ時の補正対応
- 耐久EV逆算 (`/api/battle/estimate-ev`)

#### HP追跡 (`/api/battle/hp`)

- 味方: OCR による実数値読取 (例: `149/185`)
- 相手: パーセンテージ読取 (例: `73%`)
- HPバーのピクセル解析 (HSV 色空間)
- ダメージ履歴の記録

#### まもる管理 (`/api/battle/protect`)

対応技 (16種): まもる、みきり、ニードルガード、キングシールド、トーチカ、ブロッキング、ワイドガード、ファストガード、たたみがえし、サイドチェンジ、このゆびとまれ、いかりのこな、スポットライト、ねこだまし、フェイント、よこどり

連続成功確率: 1回目=100%、2回目=33.3%、3回目=11.1%、4回目=3.7%

#### 試合管理・ターンログ

- 試合ライフサイクル: 開始 → 選出 → バトル → 終了
- フィールド条件変更時の素早さ順自動再計算
- ターン毎のアクション記録 (技・交代・テラスタル等)
- match_history / action_logs テーブルへの永続化

#### 映像解析エンジン (`/api/vision/`)

- シーンステートマシン (IDLE → MATCHING → SELECTION → BATTLE → RESULT)
- フレーム処理 (リサイズ・ROI抽出・変化検知)
- テンプレートマッチング (マルチスケール + NMS)
- OCR 基盤 (PaddleOCR 統合、テキスト自動分類)
- YOLO 検出基盤 (YOLOv10 推論パイプライン)
- WebSocket リアルタイム配信 (`/api/vision/ws`)

#### OBS 連携 (`/api/obs/`)

- WebSocket 5.x 接続・切断
- 録画制御 (開始/停止/一時停止)
- シーン切替・一覧取得
- 仮想カメラからの OpenCV フレームキャプチャ

### 5.2 フロントエンド (7ページ)

| ページ         | パス       | 概要                                                   |
| -------------- | ---------- | ------------------------------------------------------ |
| ダッシュボード | `/`        | 試合開始/終了/ターン制御 + 全パネル統合ビュー          |
| 素早さ順位     | `/speed`   | 4体入力 + フィールド条件 → 行動順表示 (トリル反転対応) |
| HP追跡         | `/hp`      | 味方: 実数値管理、相手: パーセンテージ管理             |
| まもる管理     | `/protect` | 連続成功確率 + 使用履歴表示                            |
| ダメージ計算   | `/damage`  | 第9世代準拠、STAB/範囲技/タイプ相性対応                |
| パーティ管理   | `/party`   | CRUD + JSON 入力フォーム                               |
| OBS HUD        | `/hud`     | 透明背景オーバーレイ (OBS ブラウザソース用)            |

### 5.3 テストカバレッジ

248テスト (16テストファイル):

| テストファイル              | 対象                                                   |
| --------------------------- | ------------------------------------------------------ |
| `test_speed_calculator.py`  | 素早さ計算 (追い風/トリル/スカーフ/天候/まひ/複合補正) |
| `test_damage_calculator.py` | ダメージ計算・耐久逆算                                 |
| `test_hp_tracker.py`        | HP追跡 (OCR/パーセンテージ/バー解析)                   |
| `test_protect_manager.py`   | まもる管理 (連続確率計算)                              |
| `test_battle_state.py`      | 試合状態管理                                           |
| `test_turn_logger.py`       | ターンログ記録                                         |
| `test_scene_state.py`       | シーンステートマシン遷移                               |
| `test_frame_processor.py`   | フレーム前処理・ROI抽出                                |
| `test_template_matcher.py`  | テンプレートマッチング                                 |
| `test_ocr_engine.py`        | OCRエンジン                                            |
| `test_vision_engine.py`     | 映像解析パイプライン                                   |
| `test_yolo_detector.py`     | YOLO検出                                               |
| `test_party_api.py`         | パーティ CRUD API                                      |
| `test_battle_api.py`        | バトル関連 API                                         |
| `test_vision_api.py`        | Vision API                                             |

---

## 6. 詳細設計

### 6.1 データベース設計 (Schema)

- `my_parties`: `id`, `name`, `pokemon_json(6体分)`
- `match_history`: `id`, `timestamp`, `opponent_name`, `my_party_id`, `enemy_party_json`, `result(Win/Loss)`
- `action_logs`: `match_id`, `turn`, `pokemon_slot`, `action_name`, `target_slot`

### 6.2 解析ステートマシン (Scene States)

```
IDLE → MATCHING → SELECTION → BATTLE → RESULT → IDLE
```

1.  **IDLE:** マッチング待機中。
2.  **MATCHING:** VS画面。相手の6体をスキャン。
3.  **SELECTION:** 選出画面。
4.  **BATTLE:** 対戦中。コマンド選択・演出・テキストログを監視。
5.  **RESULT:** 勝敗画面。データを保存しIDLEへ戻る。

遷移判定: フレーム解析の `SceneIndicator` (HPバー検知、コマンドメニュー検知、VS画面レイアウト検知等) に基づく。confidence 閾値 (デフォルト0.6) とノイズ耐性フレーム数 (3フレーム) を設けている。

### 6.3 ROI (関心領域) 定義

座標は正規化値 (0.0-1.0) で定義し、任意の解像度に対応。基準解像度: 1920×1080。

| ROI名             | 座標 (x, y, w, h)      | 用途                   |
| ----------------- | ---------------------- | ---------------------- |
| `hp_enemy_1`      | 0.46, 0.0, 0.24, 0.08  | 相手1体目HPエリア      |
| `hp_enemy_2`      | 0.72, 0.0, 0.24, 0.08  | 相手2体目HPエリア      |
| `hp_ally_1`       | 0.0, 0.87, 0.25, 0.11  | 味方1体目HPエリア      |
| `hp_ally_2`       | 0.25, 0.87, 0.25, 0.11 | 味方2体目HPエリア      |
| `text_box`        | 0.0, 0.75, 0.55, 0.12  | バトルログテキスト     |
| `command_menu`    | 0.78, 0.58, 0.20, 0.40 | コマンドメニュー       |
| `move_select`     | 0.58, 0.28, 0.40, 0.70 | 技選択メニュー         |
| `selection_ally`  | 0.02, 0.08, 0.28, 0.82 | 選出画面・味方リスト   |
| `selection_enemy` | 0.68, 0.03, 0.30, 0.92 | 選出画面・相手アイコン |
| `vs_icons`        | 0.68, 0.03, 0.30, 0.92 | VS画面・相手アイコン   |

### 6.4 素早さ計算ロジック

$$S_{effective} = S_{base} \times StatStageMultiplier \times Modifier_{Ability} \times Modifier_{Item} \times Modifier_{Field}$$

- `Field`: 追い風(×2)、トリックルーム(反転)、天候(すいすい等)
- `Item`: こだわりスカーフ(×1.5)、くろいてっきゅう(×0.5)等

---

## 7. 追加開発仕様書

以下は未実装の機能について、そのまま実装に着手できるレベルの詳細仕様・設計を記載する。

### Phase 5: リアルタイム映像連携パイプライン

**目的:** OBS仮想カメラからの映像フレームを Vision Engine に接続し、ゲーム状態をリアルタイムに自動認識する。

#### 5.1 OBS → Vision Engine フレーム取得

**現状:** `obs_connector.py` に OpenCV `VideoCapture` による仮想カメラ接続が実装済み。`vision_engine.py` にフレーム処理パイプラインが存在するが、OBS からの連続フレーム取得→解析ループが未結合。

**実装内容:**

```python
# backend/app/services/vision_pipeline.py (新規)

class VisionPipeline:
    """OBS仮想カメラ → Vision Engine のリアルタイム連携パイプライン。"""

    def __init__(self, vision_engine: VisionEngine, obs_connector: OBSConnector):
        self.vision_engine = vision_engine
        self.obs = obs_connector
        self.running = False
        self.target_fps = 5  # 解析FPS (映像FPSより低く設定しCPU負荷を抑える)

    async def start(self, device_index: int = 0):
        """パイプライン開始。OBS仮想カメラからフレーム取得を開始する。"""
        self.obs.start_capture(device_index)
        self.running = True
        asyncio.create_task(self._process_loop())

    async def _process_loop(self):
        """メインループ: フレーム取得 → 解析 → 状態更新 → WebSocket配信。"""
        interval = 1.0 / self.target_fps
        while self.running:
            frame = self.obs.get_frame()  # numpy.ndarray (BGR)
            if frame is not None:
                result = await self.vision_engine.process_frame(frame)
                # result に基づいてシーン遷移・HP更新・テキスト抽出を実行
                await self._dispatch_events(result)
            await asyncio.sleep(interval)

    async def _dispatch_events(self, result: FrameAnalysisResult):
        """解析結果をバトル状態管理に反映する。"""
        # 1. シーン遷移
        if result.scene_changed:
            # MATCHING → SELECTION: 相手の選出を記録
            # SELECTION → BATTLE: バトル開始
            # BATTLE → RESULT: 試合終了処理
            pass

        # 2. HP更新 (BATTLEシーン時)
        if result.hp_updates:
            for update in result.hp_updates:
                hp_tracker.update(update.slot, update.value, update.is_percentage)

        # 3. テキスト検出 (技名・特性・アイテム)
        if result.detected_texts:
            for text in result.detected_texts:
                turn_logger.log_action(text.category, text.content)
```

**APIエンドポイント追加:**

| メソッド | パス                          | 概要                                                 |
| -------- | ----------------------------- | ---------------------------------------------------- |
| POST     | `/api/vision/pipeline/start`  | パイプライン開始 (OBS仮想カメラ接続)                 |
| POST     | `/api/vision/pipeline/stop`   | パイプライン停止                                     |
| GET      | `/api/vision/pipeline/status` | パイプライン状態取得 (FPS、処理フレーム数、接続状態) |

**設定パラメータ:**

| パラメータ                   | デフォルト | 説明                                                  |
| ---------------------------- | ---------- | ----------------------------------------------------- |
| `target_fps`                 | 5          | 解析フレームレート (fps)。CPU負荷と検出精度のバランス |
| `device_index`               | 0          | OpenCV の VideoCapture デバイスインデックス           |
| `scene_confidence_threshold` | 0.6        | シーン遷移の confidence 閾値                          |
| `noise_frame_count`          | 3          | ノイズ耐性のためのフレーム数 (連続N回同じ判定で遷移)  |

**テスト計画:**

- OBS仮想カメラが未接続時のgraceful degradation (接続エラー → ステータス返却)
- フレーム取得 → VisionEngine.process_frame() の結合テスト (合成テスト画像使用)
- パイプライン開始/停止のライフサイクルテスト

---

### Phase 6: YOLOv10 モデル学習・ポケモンアイコン検出

**目的:** VS画面・選出画面でのポケモンアイコンを高精度に識別する。

#### 6.1 学習データ収集・アノテーション

**データ要件:**

| 項目               | 詳細                                                                     |
| ------------------ | ------------------------------------------------------------------------ |
| 対象ポケモン       | レギュレーション M-A 準拠の全使用可能ポケモン                            |
| 必要画像枚数       | 最低500枚 (1ポケモンあたり2-3枚 × 200種+)                                |
| 画像ソース         | OBS経由のゲーム画面キャプチャ (1920×1080)                                |
| アノテーション形式 | YOLO形式 (`class_id cx cy w h`、正規化座標)                              |
| ROI                | VS画面: `vs_icons` (0.68, 0.03, 0.30, 0.92)、選出画面: `selection_enemy` |

**データ収集スクリプト:**

```python
# backend/scripts/capture_training_data.py (新規)

"""
OBS仮想カメラからVS画面・選出画面を自動キャプチャし、
学習データを保存するスクリプト。

使い方:
  1. OBS Studio で仮想カメラを開始
  2. ゲームでランクマッチに潜る
  3. 本スクリプトを実行: uv run python scripts/capture_training_data.py
  4. VS画面/選出画面を検知すると自動保存

保存先: backend/training_data/raw/{timestamp}.png
"""

import cv2
import time
from pathlib import Path

OUTPUT_DIR = Path("training_data/raw")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

cap = cv2.VideoCapture(0)  # OBS仮想カメラ
frame_count = 0

while True:
    ret, frame = cap.read()
    if not ret:
        continue

    # VS画面/選出画面の簡易判定 (右側にアイコン列がある特徴)
    roi = frame[int(0.03*1080):int(0.95*1080), int(0.68*1920):int(0.98*1920)]
    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 50, 150)
    edge_density = edges.sum() / edges.size

    if edge_density > 30:  # アイコンが存在する可能性が高い
        filename = OUTPUT_DIR / f"{int(time.time()*1000)}.png"
        cv2.imwrite(str(filename), frame)
        frame_count += 1
        print(f"Saved: {filename} (total: {frame_count})")

    time.sleep(0.5)  # 0.5秒間隔でキャプチャ
```

#### 6.2 モデル学習

**学習設定:**

```yaml
# backend/models/pokemon_detect.yaml (新規)
# YOLOv10 学習設定ファイル

path: ../training_data
train: images/train
val: images/val

# クラス数はレギュレーション M-A の使用可能ポケモン数に依存
nc: 200 # 例: 200種

names:
  0: ガブリアス
  1: バンギラス
  2: ミミッキュ
  # ... (全ポケモンを列挙)
```

**学習コマンド:**

```bash
cd backend
uv sync --extra vision

# 学習実行
uv run yolo detect train \
  model=yolov10n.pt \
  data=models/pokemon_detect.yaml \
  epochs=100 \
  imgsz=640 \
  batch=16 \
  device=0 \
  project=models/runs \
  name=pokemon_v1

# 学習済みモデルの配置
cp models/runs/pokemon_v1/weights/best.pt models/pokemon_detect.pt
```

**既存コードとの結合:**

`yolo_detector.py` にモデルパス設定が存在する。学習済みモデルを `backend/models/pokemon_detect.pt` に配置すれば自動的に読み込まれる。

```python
# yolo_detector.py の既存コード
class YOLODetector:
    def __init__(self, model_path: str = "models/pokemon_detect.pt"):
        self.model_path = model_path
        self._model = None  # 遅延ロード
```

**テスト計画:**

- 合成テスト画像での検出テスト (既存の `test_yolo_detector.py` を拡張)
- 推論速度テスト (640×640 入力で 100ms 以下を目標)
- NMS (Non-Maximum Suppression) パラメータの調整テスト

---

### Phase 7: OCR 精度チューニング

**目的:** ゲーム画面のフォント・レイアウトに最適化したOCR設定を確立する。

#### 7.1 対象テキストと抽出パターン

| テキスト種別         | 画面位置 (ROI)                    | フォーマット例         | 抽出パターン               |
| -------------------- | --------------------------------- | ---------------------- | -------------------------- |
| 味方HP実数値         | `hp_text_ally_1/2`                | `149/185`              | `r"(\d+)/(\d+)"`           |
| 相手HPパーセンテージ | `hp_text_enemy_1/2`               | `73%`                  | `r"(\d+)%"`                |
| ポケモン名           | `name_ally_1/2`, `name_enemy_1/2` | `ガブリアス`           | 日本語テキスト全体         |
| 技名                 | `move_1/2/3/4`                    | `じしん`               | 日本語テキスト全体         |
| バトルログ           | `text_box`                        | `ガブリアスの じしん!` | 技名・特性・アイテムの分類 |
| タイマー             | `selection_timer`, `battle_timer` | `1:30`                 | `r"(\d+):(\d+)"`           |

#### 7.2 OCR前処理パイプライン

```python
# backend/app/services/ocr_engine.py の拡張

class OCRPreprocessor:
    """ゲーム画面特化のOCR前処理。"""

    @staticmethod
    def preprocess_hp_text(roi: np.ndarray) -> np.ndarray:
        """HP数値テキストの前処理。
        - グレースケール変換
        - 二値化 (OTSU) → 白文字を黒背景から分離
        - 膨張処理 → 細い数字の接続性改善
        """
        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        kernel = np.ones((2, 2), np.uint8)
        dilated = cv2.dilate(binary, kernel, iterations=1)
        return dilated

    @staticmethod
    def preprocess_pokemon_name(roi: np.ndarray) -> np.ndarray:
        """ポケモン名テキストの前処理。
        - コントラスト強調 (CLAHE)
        - 色相フィルタ → UI背景色を除去
        """
        lab = cv2.cvtColor(roi, cv2.COLOR_BGR2LAB)
        l, a, b = cv2.split(lab)
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
        cl = clahe.apply(l)
        enhanced = cv2.merge([cl, a, b])
        return cv2.cvtColor(enhanced, cv2.COLOR_LAB2BGR)

    @staticmethod
    def preprocess_battle_log(roi: np.ndarray) -> np.ndarray:
        """バトルログテキストの前処理。
        - 半透明テキストボックスの背景除去
        - アルファブレンド推定 → テキスト領域のみ抽出
        """
        hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
        # テキスト色 (白〜薄い色) のマスク
        mask = cv2.inRange(hsv, (0, 0, 180), (180, 50, 255))
        result = cv2.bitwise_and(roi, roi, mask=mask)
        return result
```

#### 7.3 PaddleOCR 設定

```python
# 推奨設定
ocr = PaddleOCR(
    use_angle_cls=False,       # ゲーム画面は回転しない
    lang="japan",              # 日本語モデル
    use_gpu=True,              # GPU使用 (可能な場合)
    det_db_thresh=0.3,         # テキスト検出閾値 (低めで取りこぼし防止)
    det_db_box_thresh=0.5,     # ボックス閾値
    rec_char_type="japan",     # 日本語文字認識
    cls_thresh=0.9,            # 分類閾値
    drop_score=0.5,            # 低スコアの結果を除外
)
```

**テスト計画:**

- 各ROIのスクリーンショットに対するOCR精度テスト (正解率90%以上を目標)
- 前処理パイプラインの効果測定 (前処理あり/なしの精度比較)
- フォントサイズ・解像度別の精度テスト

---

### Phase 8: VS画面 → 型検索連携

**目的:** VS画面で識別した相手6体のポケモンから、想定される型（持ち物・技構成・努力値配分）を自動提示する。

#### 8.1 データソース設計

```python
# backend/app/services/meta_database.py (新規)

@dataclass
class PokemonTemplate:
    """ポケモンの型テンプレート。"""
    species: str                    # 種族名
    archetype_name: str             # 型名 (例: "スカーフ型", "HB物理受け型")
    ability: str                    # 特性
    item: str                       # 持ち物
    nature: str                     # 性格
    evs: dict[str, int]            # 努力値 {"hp": 252, "attack": 252, "speed": 4}
    moves: list[str]               # 技候補 (4〜8技)
    usage_rate: float              # 使用率 (0.0-1.0)
    tera_type: str | None          # テラスタイプ
    can_mega_evolve: bool          # メガシンカ可否
    notes: str = ""                # 備考 (立ち回りのポイント等)

class MetaDatabase:
    """メタゲームデータベース。

    Game8等の外部サイトから取得した型情報を管理する。
    JSON ファイルで永続化し、定期的に更新する。
    """

    def __init__(self, data_path: str = "data/meta_templates.json"):
        self.data_path = data_path
        self.templates: dict[str, list[PokemonTemplate]] = {}
        self._load()

    def get_templates(self, species: str) -> list[PokemonTemplate]:
        """指定種族の型テンプレート一覧を使用率順で返す。"""
        return sorted(
            self.templates.get(species, []),
            key=lambda t: t.usage_rate,
            reverse=True,
        )

    def suggest_team_composition(self, enemy_species: list[str]) -> dict:
        """相手6体から想定されるパーティ構築タイプを分析する。

        Returns:
            {
                "archetype": "雨パ" | "トリルパ" | "スタン" | ...,
                "key_pokemon": [...],  # 軸となるポケモン
                "threats": [...],      # 警戒すべき要素
                "pokemon_details": {species: [PokemonTemplate, ...]}
            }
        """
        ...
```

#### 8.2 データ収集スクリプト

```python
# backend/scripts/scrape_meta_data.py (新規)

"""
Game8 等の攻略サイトからポケモンの型情報をスクレイピングし、
data/meta_templates.json に保存する。

使い方:
  uv run python scripts/scrape_meta_data.py

注意:
  - robots.txt を確認し、許可されたページのみアクセスすること
  - リクエスト間隔を3秒以上空けること
  - 取得データは個人利用の範囲に留めること
"""
```

#### 8.3 API エンドポイント

| メソッド | パス                          | 概要                                     |
| -------- | ----------------------------- | ---------------------------------------- |
| GET      | `/api/meta/pokemon/{species}` | 指定ポケモンの型テンプレート一覧         |
| POST     | `/api/meta/analyze-team`      | 相手6体の分析 (構築タイプ推定・脅威分析) |
| POST     | `/api/meta/update`            | メタデータの手動更新                     |
| GET      | `/api/meta/usage-ranking`     | 使用率ランキング                         |

**リクエスト/レスポンス例:**

```json
// POST /api/meta/analyze-team
// Request:
{
  "enemy_species": ["ガブリアス", "ペリッパー", "カマスジョー", "ミミッキュ", "バンギラス", "ドリュウズ"]
}

// Response:
{
  "archetype": "雨パ (天候変化あり)",
  "key_pokemon": [
    {"species": "ペリッパー", "role": "雨始動 (あめふらし)", "priority": "高"},
    {"species": "カマスジョー", "role": "雨エース (すいすい)", "priority": "高"}
  ],
  "threats": [
    "カマスジョーのすいすい発動時S=544 → 追い風なしでは抜けない可能性",
    "バンギラス・ドリュウズの砂パ裏選出に注意"
  ],
  "pokemon_details": {
    "ガブリアス": [
      {
        "archetype_name": "スカーフ型",
        "ability": "さめはだ",
        "item": "こだわりスカーフ",
        "moves": ["じしん", "げきりん", "ストーンエッジ", "どくづき"],
        "usage_rate": 0.45
      }
    ]
  }
}
```

**テスト計画:**

- JSON データの読み込み・検索テスト
- チーム構築タイプ推定のロジックテスト (雨パ/砂パ/トリルパ/スタン等)
- 未知のポケモンに対する graceful degradation テスト

---

### Phase 9: Electron デスクトップアプリ化

**目的:** React フロントエンドを Electron でラップし、スタンドアロンのデスクトップアプリとして配布する。

#### 9.1 技術構成

```json
// frontend/package.json に追加する依存関係
{
  "devDependencies": {
    "electron": "^33.0.0",
    "electron-builder": "^25.0.0",
    "concurrently": "^9.0.0",
    "wait-on": "^8.0.0"
  }
}
```

#### 9.2 Electron メインプロセス

```typescript
// frontend/electron/main.ts (新規)

import { app, BrowserWindow, shell } from "electron";
import { spawn, ChildProcess } from "child_process";
import path from "path";

let mainWindow: BrowserWindow | null = null;
let backendProcess: ChildProcess | null = null;

function startBackend(): void {
  // バックエンドサーバーを子プロセスとして起動
  const backendPath = path.join(__dirname, "../../backend");
  backendProcess = spawn(
    "uv",
    ["run", "uvicorn", "app.main:app", "--port", "8000"],
    {
      cwd: backendPath,
      stdio: "pipe",
    },
  );
  backendProcess.stdout?.on("data", (data) => console.log(`[backend] ${data}`));
  backendProcess.stderr?.on("data", (data) =>
    console.error(`[backend] ${data}`),
  );
}

function createWindow(): void {
  mainWindow = new BrowserWindow({
    width: 1280,
    height: 800,
    title: "PAL-C - PokeAnalysis Live for Champions",
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
    },
  });

  // 開発時: Vite dev server、本番時: ビルド済みHTML
  if (process.env.NODE_ENV === "development") {
    mainWindow.loadURL("http://localhost:5173");
  } else {
    mainWindow.loadFile(path.join(__dirname, "../dist/index.html"));
  }
}

app.whenReady().then(() => {
  startBackend();
  // バックエンド起動待ち (最大10秒)
  setTimeout(createWindow, 2000);
});

app.on("window-all-closed", () => {
  backendProcess?.kill();
  app.quit();
});
```

#### 9.3 ビルド設定

```json
// frontend/electron-builder.yml
{
  "appId": "com.palc.pokeanalyzer",
  "productName": "PAL-C",
  "directories": {
    "output": "release"
  },
  "files": ["dist/**/*", "electron/**/*"],
  "extraResources": [
    {
      "from": "../backend",
      "to": "backend",
      "filter": ["app/**/*", "models/**/*", "pyproject.toml"]
    }
  ],
  "win": {
    "target": "nsis",
    "icon": "public/icon.ico"
  },
  "mac": {
    "target": "dmg",
    "icon": "public/icon.icns"
  }
}
```

**テスト計画:**

- Electron ウィンドウの起動・終了テスト
- バックエンド子プロセスの起動・停止テスト
- ビルド成果物の動作確認 (Windows / macOS)

---

### Phase 10: CI/CD パイプライン

**目的:** GitHub Actions で自動テスト・lint・ビルドを実行する。

#### 10.1 GitHub Actions ワークフロー

```yaml
# .github/workflows/ci.yml (新規)

name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  backend-test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Install uv
        uses: astral-sh/setup-uv@v4

      - name: Set up Python
        run: uv python install 3.12

      - name: Install dependencies
        run: cd backend && uv sync --extra dev

      - name: Lint (ruff)
        run: cd backend && uv run ruff check app/ tests/

      - name: Format check (ruff)
        run: cd backend && uv run ruff format --check app/ tests/

      - name: Test (pytest)
        run: cd backend && uv run pytest -v --tb=short

  frontend-check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Setup Node.js
        uses: actions/setup-node@v4
        with:
          node-version: 22

      - name: Install dependencies
        run: cd frontend && npm ci

      - name: TypeScript check
        run: cd frontend && npx tsc --noEmit

      - name: Build
        run: cd frontend && npm run build

      - name: Lint (ESLint)
        run: cd frontend && npm run lint
```

---

## 8. 参考リソース

- **環境設定:** Game8 [ポケモンチャンピオンズ ランクマッチ概要](https://game8.jp/pokemon-champions/776525)
- **メタデータ:** レギュレーション M-A (メガシンカ・テラスタル共存ルール)
- **ポケモンアイコンソース:** [ポケモンチャンピオンズ公式 ポケモン一覧](https://web-view.app.pokemonchampions.jp/battle/pages/events/rs177501629259kmzbny/ja/pokemon.html)
- **ダメージ計算式:** 第9世代準拠 (`floor(floor(((2*Level/5+2) * Power * A/D) / 50 + 2) * Modifier * random / 100)`)
- ポケモン徹底攻略(https://yakkun.com/bbs/party/list/?rule=1)
- 対戦データ(https://champs.pokedb.tokyo/?rule=1#pokemon)
