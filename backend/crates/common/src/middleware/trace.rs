use tracing_subscriber::{fmt, prelude::*, EnvFilter};

pub fn init_tracing(service: &str) {
    let filter = EnvFilter::try_from_default_env().unwrap_or_else(|_| EnvFilter::new("info"));
    tracing_subscriber::registry()
        .with(filter)
        .with(
            fmt::layer()
                .json()
                .with_target(false)
                .with_current_span(false),
        )
        .init();
    tracing::info!(service, "tracing initialized");
}
