package com.sentinel.streaming.model;

import com.fasterxml.jackson.annotation.JsonProperty;
import java.time.Instant;

public record FeatureVector(
        @JsonProperty("endpoint") String endpoint,
        @JsonProperty("timestamp") Instant timestamp,
        @JsonProperty("request_count") int requestCount,
        @JsonProperty("latency_avg") double latencyAvg,
        @JsonProperty("req_rate_1m") double reqRate1m
) {}
