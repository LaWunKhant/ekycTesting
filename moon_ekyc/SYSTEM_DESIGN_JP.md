# MoonKYC テナントワークスペース設計書（日本語版）

## 1. 概要
本システムは、Laravel を基盤とした MoonKYC のテナント向けワークスペースである。  
テナントユーザーのログイン、顧客作成、本人確認リンク発行、テナント運用画面を担う。

一方で、顧客向け本人確認 UI、OCR/AI 処理、最終審査、スーパー管理者画面は Django 側（`Herd/PythonProject`）が担当する。

## 2. 背景
- テナント操作画面は Laravel 側に集約したい。
- 顧客本人確認フローと AI/OCR 処理は Django 側で継続運用している。
- 両アプリは同一の業務テーブルを共有するため、データ契約の維持が重要である。

## 3. 目的
| 項目 | 目的 |
|---|---|
| テナント運用 | テナント担当者が顧客作成と確認リンク発行を行えるようにする |
| 分離運用 | テナント画面は Laravel、顧客確認と最終審査は Django に分離する |
| 互換性 | 共有テーブルと URL 契約を維持し、Django 側の確認フローへ正しく引き渡す |
| 保守性 | テナント画面の改善を Laravel 側で独立して進めやすくする |

## 4. システム構成
### 4.1 論理構成
| レイヤ | 主な要素 | 役割 |
|---|---|---|
| プレゼンテーション | Inertia.js + Vue 3 + Tailwind | テナント画面を提供 |
| アプリケーション | `routes/web.php`, `Tenant*Controller` | 画面遷移、顧客作成、リンク発行 |
| ドメイン | `Tenant`, `Customer`, `VerificationLink`, `User` | 共有テーブルへのアクセス |
| データ | MySQL (`tenants`, `customers`, `kyc_verification_links`, `staff_users`) | テナント/顧客/リンク/ユーザー永続化 |
| 外部連携 | Django verification app, SMTP/Mailtrap | 本人確認画面への遷移、通知メール送信 |

### 4.2 アプリ責務分担
| アプリ | 主な責務 |
|---|---|
| Laravel (`moon_ekyc`) | テナントログイン、ダッシュボード、顧客作成、リンク発行、テナント運用画面 |
| Django (`PythonProject`) | 顧客本人確認 UI、AI/OCR、本人確認 API、スーパー管理者審査 |

## 5. 機能一覧
| 機能カテゴリ | 機能名 | 概要 | 主担当モジュール |
|---|---|---|---|
| 認証 | ログイン/登録/パスワード再設定 | テナントユーザー認証 | `routes/auth.php` |
| テナント運用 | ダッシュボード | 顧客作成と確認リンク発行 | `TenantDashboardController` |
| テナント運用 | セッション一覧 | テナント確認セッション一覧 UI | `TenantSessionsController` |
| テナント運用 | 審査キュー | テナント審査 UI | `TenantReviewController` |
| テナント運用 | チーム管理 | テナントメンバー管理 UI | `TenantTeamController` |
| 連携 | 本人確認リンク引き渡し | Django `/verify/start/<token>/` へ顧客を誘導 | `VerificationLink`, `PUBLIC_BASE_URL` |

注記:
- `sessions`, `review`, `team` は現時点では UI 雛形が中心で、実データ連携は今後強化対象である。

## 6. 画面設計
| 画面ID | 画面名 | パス | 主な利用者 | 主な機能 |
|---|---|---|---|---|
| SCR-TNT-01 | テナントダッシュボード | `/dashboard` | tenant user | 顧客作成、確認リンク発行 |
| SCR-TNT-02 | テナントセッション一覧 | `/sessions` | tenant user | セッション検索、状態確認 |
| SCR-TNT-03 | テナント審査キュー | `/review` | tenant user | テナント向け審査導線 |
| SCR-TNT-04 | テナントチーム管理 | `/team` | tenant user | メンバー表示・追加 UI |
| SCR-AUT-01 | ログイン | `/login` | tenant user | ログイン |
| SCR-AUT-02 | 登録 | `/register` | tenant user | 登録 |

## 7. データ連携設計
### 7.1 共有テーブル
| テーブル | 用途 | Laravel 側モデル |
|---|---|---|
| `tenants` | テナント情報 | `App\Models\Tenant` |
| `customers` | 顧客情報 | `App\Models\Customer` |
| `kyc_verification_links` | 顧客向け本人確認リンク | `App\Models\VerificationLink` |
| `staff_users` | テナント/管理者ユーザー | `App\Models\User` |

### 7.2 重要な連携キー
- `customers.tenant_uuid -> tenants.uuid`
- `kyc_verification_links.tenant_uuid -> tenants.uuid`
- `kyc_verification_links.customer_id -> customers.id`
- `staff_users.tenant_id -> tenants.id`

### 7.3 Django への引き渡し
1. Laravel で顧客を作成する。  
2. Laravel で `kyc_verification_links` を作成する。  
3. `<PUBLIC_BASE_URL>/verify/start/<token>/` を生成する。  
4. 顧客は Django の本人確認 UI に遷移する。  

## 8. メール送信設計
- 顧客メールアドレスがある場合のみ送信を試みる。
- SMTP 設定が不足していてもリンク自体は作成する。
- 送信失敗時は UI 上に運用メッセージを返す。
- `PUBLIC_BASE_URL` が未設定だと誤ったホストへ誘導する可能性があるため、明示設定を推奨する。

## 9. 非機能要件
### 9.1 セキュリティ要件
| 要件 | 内容 |
|---|---|
| テナント分離 | テナントユーザーは自テナントのデータのみにアクセス可能とする |
| 互換性維持 | Django と共有するテーブル名・キー・トークン契約を保護する |
| 機微情報保護 | PII や秘密情報を不用意にログ出力しない |
| 認証互換 | Django 由来の `pbkdf2_sha256` パスワードも扱えるようにする |

### 9.2 可用性/運用要件
| 要件 | 内容 |
|---|---|
| メール障害耐性 | メール送信失敗時もリンク作成自体は完了させる |
| 設定管理 | `.env` で APP_URL / PUBLIC_BASE_URL / DB / MAIL を管理する |
| 変更管理 | 共有データ契約を変える場合は Django 側ドキュメントも同時更新する |

## 10. 今後の実装強化ポイント
- `/sessions` を実データ連携へ置き換える
- `/review` に tenant 向け審査クエリ/操作を実装する
- `/team` にメンバー追加・権限変更処理を実装する
- 自己登録を維持するか、管理者招待制へ寄せるか方針を明確化する
