use axum::{extract::Request, middleware::Next, response::Response};
use metrics::{counter, histogram};
use std::time::Instant;

/// Axum middleware that records `http_requests_total` and `http_request_duration_seconds`.
pub async fn track_metrics(req: Request, next: Next) -> Response {
    let method = req.method().to_string();
    let path = req.uri().path().to_string();
    let start = Instant::now();

    let response = next.run(req).await;

    let status = response.status().as_u16().to_string();
    let elapsed = start.elapsed().as_secs_f64();

    counter!("http_requests_total",
        "method" => method.clone(),
        "path" => path.clone(),
        "status" => status.clone(),
    )
    .increment(1);

    histogram!("http_request_duration_seconds",
        "method" => method,
        "path" => path,
    )
    .record(elapsed);

    response
}
