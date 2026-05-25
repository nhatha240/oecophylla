use axum::extract::{Path, State};
use axum::http::StatusCode;
use axum::response::IntoResponse;
use axum::routing::get;
use axum::{Json, Router};
use uuid::Uuid;

use crate::db::items::{self, Item, ItemInput};
use crate::error::AppResult;
use crate::state::AppState;

pub fn router() -> Router<AppState> {
    Router::new()
        .route("/", get(list).post(create))
        .route("/{id}", get(get_one).put(update).delete(delete))
}

async fn list(State(state): State<AppState>) -> AppResult<Json<Vec<Item>>> {
    let rows = items::list(&state.pool).await?;
    Ok(Json(rows))
}

async fn create(
    State(state): State<AppState>,
    Json(input): Json<ItemInput>,
) -> AppResult<impl IntoResponse> {
    let item = items::create(&state.pool, &input).await?;
    Ok((StatusCode::CREATED, Json(item)))
}

async fn get_one(
    State(state): State<AppState>,
    Path(id): Path<Uuid>,
) -> AppResult<Json<Item>> {
    let item = items::get(&state.pool, id).await?;
    Ok(Json(item))
}

async fn update(
    State(state): State<AppState>,
    Path(id): Path<Uuid>,
    Json(input): Json<ItemInput>,
) -> AppResult<Json<Item>> {
    let item = items::update(&state.pool, id, &input).await?;
    Ok(Json(item))
}

async fn delete(
    State(state): State<AppState>,
    Path(id): Path<Uuid>,
) -> AppResult<StatusCode> {
    items::delete(&state.pool, id).await?;
    Ok(StatusCode::NO_CONTENT)
}
