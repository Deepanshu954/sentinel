package com.sentinel.streaming.model;

import com.fasterxml.jackson.annotation.JsonProperty;
import java.time.Instant;

public record FeatureVector(
        @JsonProperty("endpoint") String endpoint,
        @JsonProperty("timestamp") Instant timestamp,

        // Temporal
        @JsonProperty("hour_sin") double hourSin,
        @JsonProperty("hour_cos") double hourCos,
        @JsonProperty("dow_sin") double dowSin,
        @JsonProperty("dow_cos") double dowCos,
        @JsonProperty("week_of_year") double weekOfYear,
        @JsonProperty("is_weekend") double isWeekend,
        @JsonProperty("is_holiday") double isHoliday,
        @JsonProperty("day_of_month") double dayOfMonth,

        // Statistical
        @JsonProperty("req_rate_1m") double reqRate1m,
        @JsonProperty("req_rate_5m") double reqRate5m,
        @JsonProperty("req_rate_15m") double reqRate15m,
        @JsonProperty("req_rate_30m") double reqRate30m,
        @JsonProperty("latency_std_5m") double latencyStd5m,
        @JsonProperty("latency_std_15m") double latencyStd15m,
        @JsonProperty("req_max_5m") double reqMax5m,
        @JsonProperty("req_max_15m") double reqMax15m,
        @JsonProperty("ewma_03") double ewma03,
        @JsonProperty("ewma_07") double ewma07,
        @JsonProperty("rate_of_change") double rateOfChange,
        @JsonProperty("autocorr_lag1") double autocorrLag1,

        // Infra State
        @JsonProperty("cpu_util") double cpuUtil,
        @JsonProperty("memory_pressure") double memoryPressure,
        @JsonProperty("active_connections") double activeConnections,
        @JsonProperty("cache_hit_ratio") double cacheHitRatio,
        @JsonProperty("replica_count") double replicaCount,
        @JsonProperty("queue_depth") double queueDepth
) {}
