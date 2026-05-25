mod config;
mod db;
mod error;
mod routes;
mod state;

use std::net::SocketAddr;

use anyhow::Context;
use axum::Router;
use sqlx::postgres::PgPoolOptions;
use tokio::net::TcpListener;
use tower_http::trace::TraceLayer;
use tracing_subscriber::EnvFilter;

use crate::config::AppConfig;
use crate::state::AppState;

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    let _ = dotenvy::dotenv();

    tracing_subscriber::fmt()
        .with_env_filter(
            EnvFilter::try_from_default_env()
                .unwrap_or_else(|_| EnvFilter::new("info,backend=debug")),
        )
        .init();

    let cfg = AppConfig::from_env().context("failed to load AppConfig from environment")?;

    let pool = PgPoolOptions::new()
        .max_connections(cfg.db_max_connections)
        .connect(&cfg.database_url)
        .await
        .context("failed to connect to Postgres")?;

    sqlx::migrate!("./migrations")
        .run(&pool)
        .await
        .context("failed to run database migrations")?;

    let state = AppState { pool };

    let app: Router = Router::new()
        .merge(routes::health::router())
        .nest("/items", routes::items::router())
        .layer(TraceLayer::new_for_http())
        .with_state(state);

    let addr = SocketAddr::from(([0, 0, 0, 0], cfg.port));
    tracing::info!(%addr, "listening");

    let listener = TcpListener::bind(addr).await.context("failed to bind TCP listener")?;
    axum::serve(listener, app).await.context("server error")?;

    Ok(())
}
