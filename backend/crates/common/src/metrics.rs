use axum::response::IntoResponse;
use metrics_exporter_prometheus::PrometheusBuilder;
use std::sync::OnceLock;

static RENDER_HANDLE: OnceLock<metrics_exporter_prometheus::PrometheusHandle> = OnceLock::new();

/// Install the global Prometheus metrics recorder.
/// Call once at the top of each service's `main()`.
pub fn init_metrics() {
    let handle = PrometheusBuilder::new()
        .install_recorder()
        .expect("failed to install Prometheus recorder");
    RENDER_HANDLE.set(handle).ok();
}

/// Axum handler returning Prometheus exposition format text.
pub async fn metrics_handler() -> axum::response::Response {
    match RENDER_HANDLE.get() {
        Some(handle) => (
            axum::http::StatusCode::OK,
            [(axum::http::header::CONTENT_TYPE, "text/plain; version=0.0.4")],
            handle.render(),
        )
            .into_response(),
        None => (
            axum::http::StatusCode::SERVICE_UNAVAILABLE,
            "metrics recorder not initialized",
        )
            .into_response(),
    }
}
