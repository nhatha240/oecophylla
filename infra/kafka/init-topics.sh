#!/usr/bin/env bash
set -euo pipefail
BOOTSTRAP="${KAFKA_BROKERS:-kafka:9092}"
for topic in oecophylla.content.created oecophylla.user.followed oecophylla.interactions; do
  /opt/kafka/bin/kafka-topics.sh --bootstrap-server "$BOOTSTRAP" --create --if-not-exists --topic "$topic" --partitions 1 --replication-factor 1
done
