variable "IMAGE_TAG" {
  default = "latest"
}

variable "CARGO_DEPS_JOBS" {
  default = "8"
}

variable "CARGO_SERVICE_JOBS" {
  default = "4"
}

group "default" {
  targets = [
    "auth-service",
    "user-service",
    "content-service",
    "interaction-service",
    "feed-service",
    "moderation-service",
    "notification-service",
    "cache-invalidator",
  ]
}

group "backend" {
  targets = [
    "auth-service",
    "user-service",
    "content-service",
    "interaction-service",
    "feed-service",
    "moderation-service",
    "notification-service",
    "cache-invalidator",
  ]
}

target "_backend-common" {
  context    = "./backend"
  dockerfile = "Dockerfile"
  args = {
    CARGO_DEPS_JOBS    = CARGO_DEPS_JOBS
    CARGO_SERVICE_JOBS = CARGO_SERVICE_JOBS
  }
}

target "auth-service" {
  inherits = ["_backend-common"]
  target   = "auth-service"
  tags     = ["oecophylla-auth-service:${IMAGE_TAG}"]
}

target "user-service" {
  inherits = ["_backend-common"]
  target   = "user-service"
  tags     = ["oecophylla-user-service:${IMAGE_TAG}"]
}

target "content-service" {
  inherits = ["_backend-common"]
  target   = "content-service"
  tags     = ["oecophylla-content-service:${IMAGE_TAG}"]
}

target "interaction-service" {
  inherits = ["_backend-common"]
  target   = "interaction-service"
  tags     = ["oecophylla-interaction-service:${IMAGE_TAG}"]
}

target "feed-service" {
  inherits = ["_backend-common"]
  target   = "feed-service"
  tags     = ["oecophylla-feed-service:${IMAGE_TAG}"]
}

target "moderation-service" {
  inherits = ["_backend-common"]
  target   = "moderation-service"
  tags     = ["oecophylla-moderation-service:${IMAGE_TAG}"]
}

target "notification-service" {
  inherits = ["_backend-common"]
  target   = "notification-service"
  tags     = ["oecophylla-notification-service:${IMAGE_TAG}"]
}

target "cache-invalidator" {
  inherits = ["_backend-common"]
  target   = "cache-invalidator"
  tags     = ["oecophylla-cache-invalidator:${IMAGE_TAG}"]
}
