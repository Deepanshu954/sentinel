package com.sentinel.gate;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;

class ConfidenceGateTest {

    private ConfidenceGate gate;

    @BeforeEach
    void setUp() {
        gate = new ConfidenceGate();
        gate.setThreshold(0.75);
    }

    @Test
    void shouldDispatchWhenConfidenceMetAndRateAboveThreshold() {
        ConfidenceGate.GateDecision decision = gate.evaluate(0.80, 50.0);
        assertEquals("DISPATCH", decision.action());
        assertEquals("confidence_met", decision.reason());
    }

    @Test
    void shouldHoldWhenConfidenceBelowThreshold() {
        ConfidenceGate.GateDecision decision = gate.evaluate(0.50, 50.0);
        assertEquals("HOLD", decision.action());
        assertEquals("below_threshold", decision.reason());
    }

    @Test
    void shouldHoldWhenRateTooLow() {
        // Even with high confidence, low predicted rate should hold
        ConfidenceGate.GateDecision decision = gate.evaluate(0.90, 5.0);
        assertEquals("HOLD", decision.action());
        assertEquals("prediction_too_low", decision.reason());
    }

    @Test
    void shouldDispatchAtExactThreshold() {
        ConfidenceGate.GateDecision decision = gate.evaluate(0.75, 25.0);
        assertEquals("DISPATCH", decision.action());
    }

    @Test
    void shouldHoldJustBelowThreshold() {
        ConfidenceGate.GateDecision decision = gate.evaluate(0.749, 25.0);
        assertEquals("HOLD", decision.action());
    }

    @Test
    void shouldHoldAtExactRateThreshold() {
        // Rate of exactly 20 is considered "not low" (>= threshold check in code is <)
        ConfidenceGate.GateDecision decision = gate.evaluate(0.80, 20.0);
        assertEquals("DISPATCH", decision.action());
    }

    @Test
    void thresholdCanBeUpdatedAtRuntime() {
        gate.setThreshold(0.50);
        assertEquals(0.50, gate.getThreshold());

        ConfidenceGate.GateDecision decision = gate.evaluate(0.60, 50.0);
        assertEquals("DISPATCH", decision.action());
    }
}
