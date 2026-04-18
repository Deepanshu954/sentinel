package com.sentinel;

import org.junit.jupiter.api.Test;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.context.ActiveProfiles;

@SpringBootTest
@ActiveProfiles("test")
class SentinelOrchestratorApplicationTests {

	@Test
	void contextLoads() {
		// Verifies the Spring context loads successfully with test profile
		// (H2 in-memory DB, no Kafka/Redis connections needed)
	}

}
