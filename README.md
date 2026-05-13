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

- **Backend:** Python 3.10+, FastAPI
- **Vision:** OpenCV, PyTorch (YOLOv10), PaddleOCR
- **Frontend:** React, Tailwind CSS (Electronによるデスクトップアプリ化)
- **Database:** SQLite (SQLAlchemy)
- **Integration:** OBS WebSocket 5.x, WebSockets

---

## 4. 詳細設計

### 4.1 データベース設計 (Schema)

- `my_parties`: `id`, `name`, `pokemon_json(6体分)`
- `match_history`: `id`, `timestamp`, `opponent_name`, `my_party_id`, `enemy_party_json`, `result(Win/Loss)`
- `action_logs`: `match_id`, `turn`, `pokemon_slot`, `action_name`, `target_slot`

### 4.2 解析ステートマシン (Scene States)

1.  **IDLE:** マッチング待機中。
2.  **MATCHING:** VS画面。相手の6体をスキャン。
3.  **SELECTION:** 選出画面。
4.  **BATTLE:** 対戦中。コマンド選択・演出・テキストログを監視。
5.  **RESULT:** 勝敗画面。データを保存しIDLEへ戻る。

### 4.3 素早さ計算ロジック

$$S_{effective} = S_{base} \times Modifier_{Ability} \times Modifier_{Item} \times Modifier_{Field}$$

- `Field`: 追い風(x2)、トリックルーム(反転)、天候(すいすい等)
- `Item`: こだわりスカーフ(x1.5)、くろい鉄球(x0.5)等

---

## 5. 開発ロードマップ (Task List for Devin)

### Phase 1: 基盤構築

- [ ] FastAPIとSQLiteのセットアップ。
- [ ] 自パーティ登録用のAPIエンドポイント作成。
- [ ] OBS WebSocket 5.x との接続確認スクリプト作成。

### Phase 2: 映像解析エンジン (CV)

- [ ] OBS仮想カメラからのフレーム取得実装。
- [ ] ポケモンアイコン特定用のテンプレートマッチング/YOLO学習。
- [ ] テキストボックスOCRによる技名・特性抽出の実装。

### Phase 3: ダブルバトル・ロジック

- [ ] ターン毎の4体の素早さ順位計算機の実装。
- [ ] HPバーの変動検知とダメージ率算出ロジック。

### Phase 4: フロントエンド & オーバーレイ

- [ ] 解析結果をリアルタイム表示するReactダッシュボードの作成。
- [ ] OBSブラウザソース用のHUD(Head-Up Display)デザインと実装。

---

## 6. 参考リソース

- **環境設定:** Game8 [ポケモンチャンピオンズ ランクマッチ概要](https://game8.jp/pokemon-champions/776525)
- **メタデータ:** レギュレーション M-A (メガシンカ・テラスタル共存ルール)
