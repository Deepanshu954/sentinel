package com.sentinel.scaling;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.MediaType;
import org.springframework.http.client.JdkClientHttpRequestFactory;
import org.springframework.web.client.RestClient;

import java.net.http.HttpClient;
import java.time.Duration;
import java.util.Map;

/**
 * Scales services by calling the scaling-sidecar HTTP API,
 * which in turn runs {@code docker compose up --scale} commands.
 */
public class LocalDockerScalingExecutor implements ScalingExecutor {
    private static final Logger logger = LoggerFactory.getLogger(LocalDockerScalingExecutor.class);

    private final RestClient restClient;
    private final String targetService;

    public LocalDockerScalingExecutor(String sidecarUrl, String targetService) {
        this.targetService = targetService;

        HttpClient httpClient = HttpClient.newBuilder()
                .version(HttpClient.Version.HTTP_1_1)
                .connectTimeout(Duration.ofSeconds(5))
                .build();

        var factory = new JdkClientHttpRequestFactory(httpClient);
        factory.setReadTimeout(Duration.ofMillis(30_000)); // Scaling can take time

        this.restClient = RestClient.builder()
                .baseUrl(sidecarUrl)
                .requestFactory(factory)
                .build();
    }

    @Override
    public ScaleResult executeScaleOut(int currentReplicas, int desiredReplicas) {
        return doScale(desiredReplicas, "SCALE_OUT");
    }

    @Override
    public ScaleResult executeScaleIn(int currentReplicas, int desiredReplicas) {
        return doScale(desiredReplicas, "SCALE_IN");
    }

    private ScaleResult doScale(int desiredReplicas, String direction) {
        long start = System.currentTimeMillis();
        try {
            logger.info("{}: Requesting {} replicas of '{}'", direction, desiredReplicas, targetService);

            Map<String, Object> body = Map.of(
                "service", targetService,
                "replicas", desiredReplicas
            );

            var response = restClient.post()
                    .uri("/scale")
                    .contentType(MediaType.APPLICATION_JSON)
                    .body(body)
                    .retrieve()
                    .body(Map.class);

            long provisioningMs = System.currentTimeMillis() - start;

            // Wait briefly for replicas to become healthy, then check actual count
            Thread.sleep(Math.min(provisioningMs, 3000));
            ReplicaStatus status = getReplicaStatus();
            long totalLatency = System.currentTimeMillis() - start;

            logger.info("{}: Completed in {}ms. Desired={}, Running={}",
                    direction, totalLatency, desiredReplicas, status.running());

            return new ScaleResult(
                true, desiredReplicas, status.running(), totalLatency,
                String.format("%s to %d replicas in %dms", direction, desiredReplicas, totalLatency)
            );

        } catch (Exception e) {
            long elapsed = System.currentTimeMillis() - start;
            logger.error("{}: Failed after {}ms: {}", direction, elapsed, e.getMessage());
            return new ScaleResult(false, desiredReplicas, -1, elapsed, e.getMessage());
        }
    }

    @Override
    @SuppressWarnings("unchecked")
    public ReplicaStatus getReplicaStatus() {
        try {
            Map<String, Object> response = restClient.get()
                    .uri("/replicas?service={service}", targetService)
                    .retrieve()
                    .body(Map.class);

            if (response != null && response.containsKey(targetService)) {
                Map<String, Object> info = (Map<String, Object>) response.get(targetService);
                int total = ((Number) info.getOrDefault("total", 0)).intValue();
                int running = ((Number) info.getOrDefault("running", 0)).intValue();
                return new ReplicaStatus(total, running, targetService);
            }
            return new ReplicaStatus(0, 0, targetService);
        } catch (Exception e) {
            logger.warn("Failed to get replica status: {}", e.getMessage());
            return new ReplicaStatus(-1, -1, targetService);
        }
    }

    @Override
    public boolean isHealthy() {
        try {
            restClient.get().uri("/health").retrieve().body(Map.class);
            return true;
        } catch (Exception e) {
            return false;
        }
    }
}
