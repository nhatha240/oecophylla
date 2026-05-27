use anyhow::Context;
use chrono::{DateTime, Utc};
use sqlx::{postgres::PgRow, PgPool, Postgres, Row, Transaction};
use uuid::Uuid;

use crate::types::{AuditListItem, ReportDetail, ReportListItem};

const POST_SNIPPET_LEN: i32 = 140;

fn map_report_list_row(row: &PgRow) -> ReportListItem {
    ReportListItem {
        id: row.get("id"),
        reporter_id: row.get("reporter_id"),
        reporter_username: row.get("reporter_username"),
        post_id: row.get("post_id"),
        post_snippet: row.get("post_snippet"),
        reason: row.get("reason"),
        detail: row.get("detail"),
        status: row.get::<String, _>("status"),
        created_at: row.get("created_at"),
    }
}

fn map_audit_row(row: &PgRow) -> AuditListItem {
    AuditListItem {
        id: row.get("id"),
        actor_id: row.get("actor_id"),
        action: row.get::<String, _>("action"),
        target_type: row.get("target_type"),
        target_id: row.get("target_id"),
        report_id: row.get("report_id"),
        note: row.get("note"),
        created_at: row.get("created_at"),
    }
}

/// List reports, optionally filtered by status. When no cursor is supplied, returns
/// the most recent rows. With a cursor we use `(created_at, id) <` keyset pagination
/// so the partial `idx_reports_pending_created` index is hit when `status='pending'`.
pub async fn list_reports(
    db: &PgPool,
    status: Option<&str>,
    cursor: Option<(DateTime<Utc>, Uuid)>,
    limit: i64,
) -> anyhow::Result<Vec<ReportListItem>> {
    // We cast `status` to text in the SELECT so callers don't need to depend on
    // the report_status enum's sqlx::Type impl.
    let base = r#"
        SELECT
            r.id,
            r.reporter_id,
            u.username       AS reporter_username,
            r.post_id,
            LEFT(p.content, $LEN$) AS post_snippet,
            r.reason,
            r.detail,
            r.status::text   AS status,
            r.created_at
        FROM reports r
        LEFT JOIN users u ON u.id = r.reporter_id
        LEFT JOIN posts p ON p.id = r.post_id
    "#
    .replace("$LEN$", &POST_SNIPPET_LEN.to_string());

    let rows = match (status, cursor) {
        (Some(s), Some((ts, id))) => {
            let q = format!(
                "{base} WHERE r.status = $1::report_status \
                 AND (r.created_at, r.id) < ($2, $3) \
                 ORDER BY r.created_at DESC, r.id DESC \
                 LIMIT $4"
            );
            sqlx::query(&q)
                .bind(s)
                .bind(ts)
                .bind(id)
                .bind(limit)
                .fetch_all(db)
                .await?
        }
        (Some(s), None) => {
            let q = format!(
                "{base} WHERE r.status = $1::report_status \
                 ORDER BY r.created_at DESC, r.id DESC \
                 LIMIT $2"
            );
            sqlx::query(&q).bind(s).bind(limit).fetch_all(db).await?
        }
        (None, Some((ts, id))) => {
            let q = format!(
                "{base} WHERE (r.created_at, r.id) < ($1, $2) \
                 ORDER BY r.created_at DESC, r.id DESC \
                 LIMIT $3"
            );
            sqlx::query(&q)
                .bind(ts)
                .bind(id)
                .bind(limit)
                .fetch_all(db)
                .await?
        }
        (None, None) => {
            let q = format!("{base} ORDER BY r.created_at DESC, r.id DESC LIMIT $1");
            sqlx::query(&q).bind(limit).fetch_all(db).await?
        }
    };

    Ok(rows.iter().map(map_report_list_row).collect())
}

pub async fn get_report(db: &PgPool, id: Uuid) -> anyhow::Result<Option<ReportDetail>> {
    let row = sqlx::query(
        r#"
        SELECT
            r.id,
            r.reporter_id,
            u.username        AS reporter_username,
            r.post_id,
            p.author_id       AS post_author_id,
            LEFT(p.content, $1) AS post_snippet,
            r.reason,
            r.detail,
            r.status::text    AS status,
            r.resolved_by,
            r.resolved_at,
            r.created_at
        FROM reports r
        LEFT JOIN users u ON u.id = r.reporter_id
        LEFT JOIN posts p ON p.id = r.post_id
        WHERE r.id = $2
        "#,
    )
    .bind(POST_SNIPPET_LEN)
    .bind(id)
    .fetch_optional(db)
    .await
    .context("get_report")?;

    Ok(row.map(|row| ReportDetail {
        id: row.get("id"),
        reporter_id: row.get("reporter_id"),
        reporter_username: row.get("reporter_username"),
        post_id: row.get("post_id"),
        post_author_id: row.get("post_author_id"),
        post_snippet: row.get("post_snippet"),
        reason: row.get("reason"),
        detail: row.get("detail"),
        status: row.get("status"),
        resolved_by: row.get("resolved_by"),
        resolved_at: row.get("resolved_at"),
        created_at: row.get("created_at"),
    }))
}

pub async fn list_audit_logs(
    db: &PgPool,
    actor_id: Option<Uuid>,
    action: Option<&str>,
    cursor: Option<(DateTime<Utc>, Uuid)>,
    limit: i64,
) -> anyhow::Result<Vec<AuditListItem>> {
    let mut conds: Vec<String> = Vec::new();
    let mut bind_idx = 1usize;
    let mut actor_pos = 0usize;
    let mut action_pos = 0usize;
    let mut cursor_ts_pos = 0usize;
    let mut cursor_id_pos = 0usize;
    if actor_id.is_some() {
        actor_pos = bind_idx;
        conds.push(format!("actor_id = ${bind_idx}"));
        bind_idx += 1;
    }
    if action.is_some() {
        action_pos = bind_idx;
        conds.push(format!("action = ${bind_idx}::audit_action"));
        bind_idx += 1;
    }
    if cursor.is_some() {
        cursor_ts_pos = bind_idx;
        cursor_id_pos = bind_idx + 1;
        conds.push(format!(
            "(created_at, id) < (${ts}, ${id})",
            ts = bind_idx,
            id = bind_idx + 1
        ));
        bind_idx += 2;
    }
    let limit_pos = bind_idx;
    let where_clause = if conds.is_empty() {
        String::new()
    } else {
        format!("WHERE {}", conds.join(" AND "))
    };
    let q = format!(
        r#"SELECT
              id,
              actor_id,
              action::text AS action,
              target_type,
              target_id,
              report_id,
              note,
              created_at
           FROM audit_logs
           {where_clause}
           ORDER BY created_at DESC, id DESC
           LIMIT ${limit_pos}"#
    );

    let mut query = sqlx::query(&q);
    if actor_pos > 0 {
        query = query.bind(actor_id.unwrap());
    }
    if action_pos > 0 {
        query = query.bind(action.unwrap());
    }
    if cursor_ts_pos > 0 {
        let (ts, id) = cursor.unwrap();
        query = query.bind(ts).bind(id);
        // suppress unused-variable lint
        let _ = cursor_id_pos;
    }
    let rows = query.bind(limit).fetch_all(db).await?;
    Ok(rows.iter().map(map_audit_row).collect())
}

/// Recent reports targeting a user (joined via post.author).
pub async fn user_report_history(
    db: &PgPool,
    user_id: Uuid,
    limit: i64,
) -> anyhow::Result<Vec<ReportListItem>> {
    let rows = sqlx::query(
        r#"
        SELECT
            r.id,
            r.reporter_id,
            ru.username       AS reporter_username,
            r.post_id,
            LEFT(p.content, $1) AS post_snippet,
            r.reason,
            r.detail,
            r.status::text    AS status,
            r.created_at
        FROM reports r
        JOIN posts p ON p.id = r.post_id
        LEFT JOIN users ru ON ru.id = r.reporter_id
        WHERE p.author_id = $2
        ORDER BY r.created_at DESC, r.id DESC
        LIMIT $3
        "#,
    )
    .bind(POST_SNIPPET_LEN)
    .bind(user_id)
    .bind(limit)
    .fetch_all(db)
    .await?;
    Ok(rows.iter().map(map_report_list_row).collect())
}

pub async fn user_audit_history(
    db: &PgPool,
    user_id: Uuid,
    limit: i64,
) -> anyhow::Result<Vec<AuditListItem>> {
    let rows = sqlx::query(
        r#"
        SELECT
            id,
            actor_id,
            action::text AS action,
            target_type,
            target_id,
            report_id,
            note,
            created_at
        FROM audit_logs
        WHERE (target_type = 'user' AND target_id = $1)
           OR (target_type = 'post' AND target_id IN (SELECT id FROM posts WHERE author_id = $1))
        ORDER BY created_at DESC, id DESC
        LIMIT $2
        "#,
    )
    .bind(user_id)
    .bind(limit)
    .fetch_all(db)
    .await?;
    Ok(rows.iter().map(map_audit_row).collect())
}

/// Row returned by the FOR UPDATE locking SELECT inside resolve_report. We need
/// the report's current status (to enforce idempotency) and the post's author
/// (so ban_author can flip is_active) inside the same transaction.
pub struct LockedReport {
    pub id: Uuid,
    pub status: String,
    pub post_id: Uuid,
    pub post_author_id: Uuid,
}

pub async fn lock_report_for_resolve(
    tx: &mut Transaction<'_, Postgres>,
    report_id: Uuid,
) -> anyhow::Result<Option<LockedReport>> {
    let row = sqlx::query(
        r#"
        SELECT r.id,
               r.status::text AS status,
               r.post_id,
               p.author_id    AS post_author_id
        FROM reports r
        JOIN posts p ON p.id = r.post_id
        WHERE r.id = $1
        FOR UPDATE OF r
        "#,
    )
    .bind(report_id)
    .fetch_optional(&mut **tx)
    .await
    .context("lock_report_for_resolve")?;

    Ok(row.map(|row| LockedReport {
        id: row.get("id"),
        status: row.get("status"),
        post_id: row.get("post_id"),
        post_author_id: row.get("post_author_id"),
    }))
}

pub async fn set_report_status(
    tx: &mut Transaction<'_, Postgres>,
    report_id: Uuid,
    new_status: &str,
    resolved_by: Uuid,
) -> anyhow::Result<()> {
    sqlx::query(
        r#"UPDATE reports
           SET status = $1::report_status,
               resolved_by = $2,
               resolved_at = NOW()
           WHERE id = $3"#,
    )
    .bind(new_status)
    .bind(resolved_by)
    .bind(report_id)
    .execute(&mut **tx)
    .await
    .context("set_report_status")?;
    Ok(())
}

pub async fn hide_post(tx: &mut Transaction<'_, Postgres>, post_id: Uuid) -> anyhow::Result<()> {
    sqlx::query("UPDATE posts SET status = 'hidden' WHERE id = $1")
        .bind(post_id)
        .execute(&mut **tx)
        .await
        .context("hide_post")?;
    Ok(())
}

pub async fn deactivate_user(
    tx: &mut Transaction<'_, Postgres>,
    user_id: Uuid,
) -> anyhow::Result<()> {
    sqlx::query("UPDATE users SET is_active = false WHERE id = $1")
        .bind(user_id)
        .execute(&mut **tx)
        .await
        .context("deactivate_user")?;
    Ok(())
}

pub async fn insert_audit_log(
    tx: &mut Transaction<'_, Postgres>,
    actor_id: Uuid,
    action: &str,
    target_type: &str,
    target_id: Uuid,
    report_id: Option<Uuid>,
    note: Option<&str>,
) -> anyhow::Result<Uuid> {
    let row = sqlx::query(
        r#"INSERT INTO audit_logs (actor_id, action, target_type, target_id, report_id, note)
           VALUES ($1, $2::audit_action, $3, $4, $5, $6)
           RETURNING id"#,
    )
    .bind(actor_id)
    .bind(action)
    .bind(target_type)
    .bind(target_id)
    .bind(report_id)
    .bind(note)
    .fetch_one(&mut **tx)
    .await
    .context("insert_audit_log")?;
    Ok(row.get("id"))
}
