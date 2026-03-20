package com.sentinel.client;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.MediaType;
import org.springframework.http.client.JdkClientHttpRequestFactory;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestClient;

import java.net.http.HttpClient;
import java.time.Duration;
import java.util.List;
import java.util.Map;
import java.util.Optional;

@Component
public class MLServiceClient {
    private static final Logger logger = LoggerFactory.getLogger(MLServiceClient.class);
    private static final int MAX_RETRIES = 2;
    private static final long RETRY_DELAY_MS = 200;
    private final RestClient restClient;

    public MLServiceClient(@Value("${ML_SERVICE_URL:http://ml-service:8000}") String mlServiceUrl) {
        HttpClient httpClient = HttpClient.newBuilder()
                .version(HttpClient.Version.HTTP_1_1)
                .connectTimeout(Duration.ofSeconds(5))
                .build();

        var factory = new JdkClientHttpRequestFactory(httpClient);
        factory.setReadTimeout(Duration.ofMillis(5000));
        
        this.restClient = RestClient.builder()
                .baseUrl(mlServiceUrl)
                .requestFactory(factory)
                .build();
    }

    public Optional<PredictionResponse> predict(List<Double> features) {
        for (int attempt = 0; attempt <= MAX_RETRIES; attempt++) {
            try {
                PredictionResponse response = restClient.post()
                        .uri("/predict")
                        .contentType(MediaType.APPLICATION_JSON)
                        .body(Map.of("features", features))
                        .retrieve()
                        .body(PredictionResponse.class);
                return Optional.ofNullable(response);
            } catch (Exception e) {
                if (attempt < MAX_RETRIES) {
                    logger.warn("ML service /predict attempt {} failed ({}), retrying...", attempt + 1, e.getMessage());
                    try { Thread.sleep(RETRY_DELAY_MS * (attempt + 1)); } catch (InterruptedException ie) { Thread.currentThread().interrupt(); }
                } else {
                    logger.error("Failed to call ML service /predict after {} attempts: {}", MAX_RETRIES + 1, e.getMessage());
                }
            }
        }
        return Optional.empty();
    }

    public record PredictionResponse(
            double predicted_req_rate,
            double lower_bound,
            double upper_bound,
            double confidence,
            String action,
            double threshold_used
    ) {}
}
