package com.sentinel.scheduler;

import com.sentinel.client.InfluxDBReader;
import com.sentinel.client.MLServiceClient;
import com.sentinel.client.MLServiceClient.PredictionResponse;
import com.sentinel.dispatcher.ActionDispatcher;
import com.sentinel.gate.ConfidenceGate;
import com.sentinel.gate.ConfidenceGate.GateDecision;
import com.sentinel.model.ScalingAction;
import com.sentinel.repository.ScalingActionRepository;
import io.micrometer.core.instrument.MeterRegistry;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;
import org.springframework.transaction.annotation.Transactional;

import java.time.Instant;
import java.util.List;
import java.util.Optional;
import java.util.concurrent.atomic.AtomicReference;

@Component
public class PredictionScheduler {
    private static final Logger logger = LoggerFactory.getLogger(PredictionScheduler.class);

    private final InfluxDBReader influxDBReader;
    private final MLServiceClient mlServiceClient;
    private final ConfidenceGate confidenceGate;
    private final ActionDispatcher actionDispatcher;
    private final ScalingActionRepository scalingActionRepository;
    private final AtomicReference<Double> confidenceGaugeRef = new AtomicReference<>(0.0);

    public PredictionScheduler(InfluxDBReader influxDBReader,
                               MLServiceClient mlServiceClient,
                               ConfidenceGate confidenceGate,
                               ActionDispatcher actionDispatcher,
                               ScalingActionRepository scalingActionRepository,
                               MeterRegistry meterRegistry) {
        this.influxDBReader = influxDBReader;
        this.mlServiceClient = mlServiceClient;
        this.confidenceGate = confidenceGate;
        this.actionDispatcher = actionDispatcher;
        this.scalingActionRepository = scalingActionRepository;
        
        meterRegistry.gauge("sentinel_ml_confidence_score", confidenceGaugeRef, AtomicReference::get);
    }

    @Scheduled(fixedRateString = "${sentinel.polling.interval.ms:5000}")
    @Transactional
    public void executePredictionCycle() {
        long startTime = System.currentTimeMillis();
        
        logger.info("Reading features from InfluxDB...");
        Optional<List<Double>> featuresOpt = influxDBReader.getLatestFeatureVector();
        if (featuresOpt.isEmpty()) {
            logger.warn("InfluxDB unavailable or no recent data found. Skipping ML prediction cycle.");
            return;
        }

        List<Double> features = featuresOpt.get();
        logger.info("Got {} features from InfluxDB", features.size());
        
        if (features.size() != 26) {
            logger.warn("Invalid feature vector size: {}, expected 26. Skipping ML prediction cycle.", features.size());
            return;
        }

        Optional<PredictionResponse> predictionOpt = mlServiceClient.predict(features);
        if (predictionOpt.isEmpty()) {
            logger.error("ML Service unavailable or failed. Skipping ML prediction cycle.");
            return;
        }

        PredictionResponse prediction = predictionOpt.get();
        logger.info("Prediction: rate={} confidence={} action={}", prediction.predicted_req_rate(), prediction.confidence(), prediction.action());
        
        confidenceGaugeRef.set(prediction.confidence());
        
        GateDecision decision = confidenceGate.evaluate(prediction.confidence(), prediction.predicted_req_rate());
        
        if ("DISPATCH".equals(decision.action())) {
            actionDispatcher.dispatch(prediction);
        } else {
            logger.info("HOLD: Prediction confidence or rate didn't meet thresholds. Reason: {}, Confidence: {}", 
                    decision.reason(), decision.confidence());
        }
        
        long durationMs = System.currentTimeMillis() - startTime;
        
        ScalingAction record = new ScalingAction();
        record.setTimestamp(Instant.now());
        record.setActionType(decision.action());
        record.setConfidence(decision.confidence());
        record.setPredictedRate(prediction.predicted_req_rate());
        record.setReason(decision.reason());
        record.setDurationMs(durationMs);
        
        scalingActionRepository.save(record);
    }
}
