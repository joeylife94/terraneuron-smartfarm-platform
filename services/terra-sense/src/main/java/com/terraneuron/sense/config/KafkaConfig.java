package com.terraneuron.sense.config;

import org.apache.kafka.clients.admin.NewTopic;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.kafka.config.TopicBuilder;

/**
 * Kafka 설정
 */
@Configuration
public class KafkaConfig {

    @Value("${kafka.topic.raw-sensor-data}")
    private String rawSensorDataTopic;

    @Bean
    public NewTopic rawSensorDataTopic() {
        return TopicBuilder.name(rawSensorDataTopic)
                .partitions(3)
                .replicas(1)
                .build();
    }
}
