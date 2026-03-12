# MoonKYC システム設計書（日本語版）

## 1. 概要
本システムは、Django を基盤としたマルチテナント対応の eKYC（本人確認）プラットフォームである。  
テナント企業ごとに顧客の本人確認セッションを発行し、書類撮影・なりすまし防止（Liveness）・顔照合・OCR 支援を経て、最終的に人手審査で承認判定を行う。

## 2. 背景
- 金融/決済/会員基盤における本人確認の厳格化が求められている。
- 自動化のみでは誤判定リスクがあるため、AI は補助に留め、最終判定を審査担当者が行う運用が必要である。
- テナント分離（企業単位のデータ隔離）と監査可能性（いつ誰が何を判断したか）が必須である。

## 3. 目的
| 項目 | 目的 |
|---|---|
| 本人確認品質 | 顔照合・Liveness・OCR により審査効率を向上しつつ、誤判定を抑制する |
| 運用性 | 審査一覧/詳細画面での迅速な確認とステータス更新を可能にする |
| 監査性 | `review_status` 変更と AI 補助結果を `document_data` に保存し追跡可能とする |
| テナント分離 | 非プラットフォーム管理者は所属テナントデータのみにアクセス可能とする |

## 4. システム構成
### 4.1 論理構成
| レイヤ | 主な要素 | 役割 |
|---|---|---|
| プレゼンテーション | Django Template + Tailwind | 管理画面/審査画面/顧客入力画面を提供 |
| アプリケーション | `kyc/views.py`, `kyc/api_views.py` | 業務ロジック、API 提供、画面遷移制御 |
| ドメインサービス | `kyc/services/mistral_ai.py`, `kyc/services/card_physical_check.py` | OCR 非同期処理、物理カード性チェック |
| データ | MySQL (`tenants`, `customers`, `kyc_sessions`, `kyc_verification_links`) | 業務データ永続化 |
| 外部連携 | Mistral OCR API, Mailtrap/SMTP | OCR 実行、通知メール送信 |

### 4.2 運用上の前提
- DB は MySQL のみを使用する（`DB_ENGINE=mysql`）。
- OCR は非同期ワーカーで実行し、顧客 submit 処理はブロッキングしない。
- OCR 失敗/レート制限時はキュー再試行（指数バックオフ）する。

## 5. 機能一覧
| 機能カテゴリ | 機能名 | 概要 | 主担当モジュール |
|---|---|---|---|
| 認証 | ログイン/ログアウト/パスワード変更 | ユーザー認証とセッション管理 | `accounts` |
| テナント管理 | ダッシュボード/メンバー管理 | テナント単位の運用管理 | `kyc/views.py` |
| 顧客導線 | 検証リンク発行 | 顧客向け本人確認開始 URL を発行 | `VerificationLink`, `tenant_dashboard` |
| セッション管理 | 開始/状態参照/提出 | 本人確認セッション API を提供 | `start_session`, `session_status`, `submit_session` |
| 撮影 | 書類表裏/セルフィー/傾き | 画像取得と保存 | `capture_image`, `capture_document` |
| Liveness | 開始/結果保存/キャンセル | なりすまし防止判定 | `start_liveness`, `save_liveness_result` |
| AI補助 | 顔照合・物理カード性 | スコア算出と補助判定 | `verify_kyc`, `card_physical_check` |
| OCR補助 | Mistral OCR 非同期実行 | 表裏 OCR・住所統合・品質フラグ付与 | `mistral_ai.py` |
| 審査 | 審査一覧/審査詳細/判定更新 | 最終判定（手動）を実施 | `review_sessions`, `review_session_detail` |

## 6. 画面設計
| 画面ID | 画面名 | パス | 主な利用者 | 主な機能 |
|---|---|---|---|---|
| SCR-ADM-01 | プラットフォーム管理ダッシュボード | `/admin/dashboard/` | super_admin | 全体状況、テナント管理 |
| SCR-TNT-01 | テナントダッシュボード | `/<tenant_slug>/dashboard/` | owner/admin/staff | 顧客作成、検証リンク発行 |
| SCR-TNT-02 | テナントセッション一覧 | `/<tenant_slug>/sessions/` | owner/admin/staff | セッション一覧、状態確認 |
| SCR-RVW-01 | 審査一覧 | `/review/` | super_admin/tenant reviewer | 審査対象検索、詳細遷移 |
| SCR-RVW-02 | 審査詳細 | `/review/<session_id>/` | super_admin/tenant reviewer | 画像確認、`review_status` 更新 |
| SCR-CUS-01 | 顧客本人確認開始 | `/verify/start/<token>/` | customer | 本人確認フロー開始 |
| SCR-CUS-02 | 顧客本人確認画面 | `/verify/` | customer | 入力、撮影、Liveness、提出 |

### 6.1 画面遷移補足
- 審査詳細の「Back to list」は、  
  - super_admin: 審査一覧へ遷移  
  - テナントユーザー: テナントセッション一覧へ遷移

## 7. API設計
### 7.1 主要API一覧
| API名 | Method | Path | 概要 | 主な正常応答 |
|---|---|---|---|---|
| セッション開始 | POST | `/session/start` | セッション発行 | `{"success": true, "session_id": "...", "status": "started"}` |
| セッション状態 | GET | `/session/status/<session_id>` | 状態参照 | `{"success": true, "session": {...}}` |
| セッション提出 | POST | `/session/submit` | 顧客情報/書類情報保存、提出状態化 | `{"success": true, "status": "submitted"}` |
| 画像保存 | POST | `/capture/` | base64 画像保存 | `{"success": true, "path": ...}` |
| Liveness結果保存 | POST | `/liveness-result` | Liveness 判定保存 | `{"success": true}` |
| 本人確認実行 | POST | `/verify/submit/` | 顔照合・物理判定・OCRキュー投入 | `{"success": true, ...}` |
| Liveness開始 | POST | `/start-liveness/` | Liveness 実行状態開始 | `{"success": true}` |
| Liveness確認 | POST | `/check-liveness/` | 実行状態確認 | `{"success": true, ...}` |
| Liveness中止 | POST | `/cancel-liveness/` | 実行状態キャンセル | `{"success": true}` |

### 7.2 エラー設計方針
| 区分 | ステータス | 例 |
|---|---|---|
| 入力不備 | 400 | `session_id` 欠落、tenant 不正 |
| 認可/範囲外 | 403 | テナント外セッション参照 |
| データ未存在 | 404 | セッション/顧客未存在 |
| サーバ内部 | 500 | 外部API例外、予期せぬ処理失敗 |

## 8. データベース設計
### 8.1 テーブル一覧
| テーブル名 | 概要 | 主キー |
|---|---|---|
| `tenants` | テナント情報 | `id` |
| `customers` | 顧客情報（テナント配下） | `id` |
| `kyc_sessions` | 本人確認セッション | `id(UUID)` |
| `kyc_verification_links` | 顧客向け検証リンク | `id` |

### 8.2 主要項目（抜粋）
| テーブル | 項目 | 型/内容 | 備考 |
|---|---|---|---|
| `customers` | `tenant_uuid` | FK | テナント分離キー |
| `customers` | `full_name`, `date_of_birth`, `postal_code` 等 | 顧客属性 | 申告情報 |
| `kyc_sessions` | `status`, `current_step` | 進行状態 | セッション状態管理 |
| `kyc_sessions` | `front_image`, `back_image`, `selfie_image` | 画像パス | 撮影結果 |
| `kyc_sessions` | `verify_similarity`, `liveness_verified` | 自動判定結果 | AI補助 |
| `kyc_sessions` | `review_status`, `reviewed_by`, `reviewed_at` | 手動審査結果 | 最終判定監査 |
| `kyc_sessions` | `document_data(JSON)` | OCR/AI補助詳細 | 監査ログ兼拡張領域 |

### 8.3 `document_data` 管理方針
- `ai_document_extraction.front/back`: OCR 生データ + 品質フラグ
- `ai_document_extraction.address_summary`: 表裏住所統合結果
- `identity_assist`: スコア、推奨、品質課題（`quality_issues`）

## 9. 処理フロー
### 9.1 顧客本人確認フロー
1. テナントユーザーが顧客作成・検証リンク発行。  
2. 顧客がリンクから本人確認画面を開始。  
3. セッション開始 (`/session/start`)。  
4. 顧客情報入力・書類表裏撮影・Liveness・セルフィー撮影。  
5. 提出 (`/session/submit`)。  
6. 本人確認実行 (`/verify/submit/`)。  
7. OCR は非同期キューで実行し、`document_data` に反映。  
8. 審査担当者が `/review/` から詳細確認し最終判定。

### 9.2 OCR非同期フロー
1. `verify_kyc` で OCR ジョブをキュー投入。  
2. ワーカーが front/back OCR を実行。  
3. 429 発生時は指数バックオフで再投入。  
4. 抽出結果を正規化し、住所統合・品質フラグを付与。  
5. `identity_assist` を再計算しセッションへ保存。

## 10. 非機能要件
### 10.1 セキュリティ要件
| 要件 | 内容 |
|---|---|
| テナント分離 | 非 super_admin は `request.user.tenant` スコープ必須 |
| 最終判定の統制 | AI は補助のみ。`review_status` は手動更新を原則とする |
| 機微情報保護 | PII/秘密情報の平文ログ出力を禁止 |
| 監査性 | 判定履歴・AI補助情報を追跡可能な形で保存 |

### 10.2 可用性/性能要件
| 要件 | 内容 |
|---|---|
| 応答性 | 顧客提出は OCR 完了待ちを行わず即時応答 |
| リトライ | OCR 429 に対してキュー再試行 + バックオフ |
| 拡張性 | `document_data(JSON)` による段階的項目拡張を許容 |

### 10.3 運用・保守要件
| 要件 | 内容 |
|---|---|
| 設定管理 | `.env` による環境差分管理（DB/SMTP/OCR） |
| 障害解析 | セッションID起点で `document_data`・審査履歴を確認可能 |
| 変更管理 | 挙動変更時は README/設計書を同時更新する |
