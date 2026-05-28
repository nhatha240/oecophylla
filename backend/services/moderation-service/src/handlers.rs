use axum::{
    extract::{Path, Query, State},
    http::StatusCode,
    response::IntoResponse,
    Extension, Json,
};
use common::{
    error::{AppError, AppResult},
    events::{Envelope, ModerationAction, TOPIC_MODERATION_ACTION},
    models::AuthUser,
};
use serde::Serialize;
use uuid::Uuid;

use crate::{
    cursor, repo,
    state::AppState,
    types::{
        AuditListQuery, AuditListResponse, ReportDetail, ReportListQuery, ReportListResponse,
        ResolveAction, ResolveRequest, ResolveResponse, UserHistoryResponse,
    },
};

const DEFAULT_LIMIT: usize = 20;
const MAX_LIMIT: usize = 100;
const HISTORY_LIMIT: i64 = 50;

fn clamp_limit(raw: Option<usize>) -> i64 {
    raw.unwrap_or(DEFAULT_LIMIT).clamp(1, MAX_LIMIT) as i64
}

// ---------- GET /admin/reports ----------

pub async fn list_reports(
    State(s): State<AppState>,
    Query(q): Query<ReportListQuery>,
) -> AppResult<Json<ReportListResponse>> {
    let limit = clamp_limit(q.limit);
    let cursor = q.cursor.as_deref().and_then(cursor::decode);
    let status = q.status.as_deref();

    let mut items = repo::list_reports(&s.db, status, cursor, limit + 1)
        .await
        .map_err(AppError::Other)?;

    let next_cursor = if items.len() as i64 > limit {
        items.pop();
        items
            .last()
            .map(|item| cursor::encode(item.created_at, item.id))
    } else {
        None
    };

    Ok(Json(ReportListResponse { items, next_cursor }))
}

// ---------- GET /admin/reports/:id ----------

pub async fn get_report(
    State(s): State<AppState>,
    Path(id): Path<Uuid>,
) -> AppResult<Json<ReportDetail>> {
    let r = repo::get_report(&s.db, id)
        .await
        .map_err(AppError::Other)?
        .ok_or(AppError::NotFound {
            kind: "report".into(),
        })?;
    Ok(Json(r))
}

// ---------- GET /admin/audit-logs ----------

pub async fn list_audit_logs(
    State(s): State<AppState>,
    Query(q): Query<AuditListQuery>,
) -> AppResult<Json<AuditListResponse>> {
    let limit = clamp_limit(q.limit);
    let cursor = q.cursor.as_deref().and_then(cursor::decode);
    let action = q.action.as_deref();

    let mut items = repo::list_audit_logs(&s.db, q.actor_id, action, cursor, limit + 1)
        .await
        .map_err(AppError::Other)?;

    let next_cursor = if items.len() as i64 > limit {
        items.pop();
        items
            .last()
            .map(|item| cursor::encode(item.created_at, item.id))
    } else {
        None
    };

    Ok(Json(AuditListResponse { items, next_cursor }))
}

// ---------- GET /admin/users/:id/history ----------

pub async fn user_history(
    State(s): State<AppState>,
    Path(user_id): Path<Uuid>,
) -> AppResult<Json<UserHistoryResponse>> {
    let reports = repo::user_report_history(&s.db, user_id, HISTORY_LIMIT)
        .await
        .map_err(AppError::Other)?;
    let audit_entries = repo::user_audit_history(&s.db, user_id, HISTORY_LIMIT)
        .await
        .map_err(AppError::Other)?;
    Ok(Json(UserHistoryResponse {
        user_id,
        reports,
        audit_entries,
    }))
}

// ---------- POST /admin/reports/:id/resolve ----------

struct Outcome {
    new_status: &'static str,
    audit_action: &'static str,
    audit_target_type: &'static str,
    event_type: &'static str,
}

fn outcome_for(action: &ResolveAction) -> Outcome {
    match action {
        ResolveAction::Dismiss => Outcome {
            new_status: "resolved_ok",
            audit_action: "report_dismissed",
            audit_target_type: "report",
            event_type: "report_dismissed",
        },
        ResolveAction::HidePost => Outcome {
            new_status: "resolved_hidden",
            audit_action: "post_hidden",
            audit_target_type: "post",
            event_type: "post_hidden",
        },
        ResolveAction::WarnAuthor => Outcome {
            new_status: "resolved_warned",
            audit_action: "author_warned",
            audit_target_type: "user",
            event_type: "author_warned",
        },
        ResolveAction::BanAuthor => Outcome {
            new_status: "resolved_warned",
            audit_action: "author_banned",
            audit_target_type: "user",
            event_type: "author_banned",
        },
    }
}

pub async fn resolve_report(
    State(s): State<AppState>,
    Extension(admin): Extension<AuthUser>,
    Path(report_id): Path<Uuid>,
    Json(body): Json<ResolveRequest>,
) -> AppResult<impl IntoResponse> {
    let outcome = outcome_for(&body.action);

    let mut tx = s.db.begin().await?;

    let locked = repo::lock_report_for_resolve(&mut tx, report_id)
        .await
        .map_err(AppError::Other)?
        .ok_or(AppError::NotFound {
            kind: "report".into(),
        })?;

    if locked.status != "pending" {
        // Roll back the read-only lock and signal idempotency violation.
        let _ = tx.rollback().await;
        return Err(AppError::Conflict {
            kind: "report_already_resolved".into(),
        });
    }

    repo::set_report_status(&mut tx, locked.id, outcome.new_status, admin.id)
        .await
        .map_err(AppError::Other)?;

    let audit_target_id: Uuid = match body.action {
        ResolveAction::Dismiss => locked.id,
        ResolveAction::HidePost => {
            repo::hide_post(&mut tx, locked.post_id)
                .await
                .map_err(AppError::Other)?;
            locked.post_id
        }
        ResolveAction::WarnAuthor => locked.post_author_id,
        ResolveAction::BanAuthor => {
            repo::deactivate_user(&mut tx, locked.post_author_id)
                .await
                .map_err(AppError::Other)?;
            locked.post_author_id
        }
    };

    repo::insert_audit_log(
        &mut tx,
        admin.id,
        outcome.audit_action,
        outcome.audit_target_type,
        audit_target_id,
        Some(locked.id),
        body.note.as_deref(),
    )
    .await
    .map_err(AppError::Other)?;

    tx.commit().await?;

    // Kafka publish happens after commit. Failure logs + increments a counter
    // but does not unwind the transaction.
    let key = locked.id.to_string();
    let envelope = Envelope::new(
        outcome.event_type,
        "moderation-service",
        ModerationAction {
            actor_id: admin.id,
            target_user_id: locked.post_author_id,
            target_post_id: Some(locked.post_id),
            report_id: Some(locked.id),
            note: body.note.clone(),
        },
    );
    s.kafka
        .produce_json(&s.mod_cfg.moderation_topic, &key, &envelope)
        .await;
    let _ = TOPIC_MODERATION_ACTION; // keep symbol used for grep + ensures const stays linked.

    tracing::info!(
        report_id = %locked.id,
        admin = %admin.id,
        action = outcome.event_type,
        "moderation action committed"
    );

    Ok((
        StatusCode::OK,
        Json(ResolveResponse {
            report_id: locked.id,
            status: outcome.new_status.into(),
            action: outcome.event_type.into(),
        }),
    ))
}

// ---------- GET /admin/metrics ----------

#[derive(Serialize)]
pub struct DashboardMetrics {
    pub total_users: i64,
    pub total_posts: i64,
    pub total_interactions: i64,
    pub posts_last_24h: i64,
    pub posts_last_7d: i64,
    pub active_users_24h: i64,
    pub pending_reports: i64,
}

pub async fn admin_metrics(
    State(s): State<AppState>,
) -> AppResult<Json<DashboardMetrics>> {
    let total_users: i64 =
        sqlx::query_scalar("SELECT count(*) FROM users")
            .fetch_one(&s.db)
            .await
            .map_err(|e| AppError::Other(e.into()))?;
    let total_posts: i64 =
        sqlx::query_scalar("SELECT count(*) FROM posts")
            .fetch_one(&s.db)
            .await
            .map_err(|e| AppError::Other(e.into()))?;
    let total_interactions: i64 =
        sqlx::query_scalar("SELECT count(*) FROM interactions")
            .fetch_one(&s.db)
            .await
            .map_err(|e| AppError::Other(e.into()))?;
    let posts_last_24h: i64 =
        sqlx::query_scalar("SELECT count(*) FROM posts WHERE created_at > now() - interval '24 hours'")
            .fetch_one(&s.db)
            .await
            .map_err(|e| AppError::Other(e.into()))?;
    let posts_last_7d: i64 =
        sqlx::query_scalar("SELECT count(*) FROM posts WHERE created_at > now() - interval '7 days'")
            .fetch_one(&s.db)
            .await
            .map_err(|e| AppError::Other(e.into()))?;
    let active_users_24h: i64 =
        sqlx::query_scalar("SELECT count(DISTINCT user_id) FROM interactions WHERE created_at > now() - interval '24 hours'")
            .fetch_one(&s.db)
            .await
            .map_err(|e| AppError::Other(e.into()))?;
    let pending_reports: i64 =
        sqlx::query_scalar("SELECT count(*) FROM reports WHERE status = 'pending'")
            .fetch_one(&s.db)
            .await
            .map_err(|e| AppError::Other(e.into()))?;

    Ok(Json(DashboardMetrics {
        total_users,
        total_posts,
        total_interactions,
        posts_last_24h,
        posts_last_7d,
        active_users_24h,
        pending_reports,
    }))
}
