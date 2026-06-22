package com.terraneuron.ops.config;

import lombok.extern.slf4j.Slf4j;
import org.apache.kafka.common.TopicPartition;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.autoconfigure.kafka.ConcurrentKafkaListenerContainerFactoryConfigurer;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.kafka.config.ConcurrentKafkaListenerContainerFactory;
import org.springframework.kafka.config.TopicBuilder;
import org.springframework.kafka.core.ConsumerFactory;
import org.springframework.kafka.core.KafkaTemplate;
import org.springframework.kafka.core.KafkaAdmin.NewTopics;
import org.springframework.kafka.listener.DeadLetterPublishingRecoverer;
import org.springframework.kafka.listener.DefaultErrorHandler;
import org.springframework.util.backoff.FixedBackOff;

@Slf4j
@Configuration
public class KafkaConsumerConfig {

    static final String DLT_SUFFIX = ".DLT";

    private final long retryBackoffMs;
    private final long maxRetries;

    public KafkaConsumerConfig(
            @Value("${app.kafka.retry.backoff-ms:1000}") long retryBackoffMs,
            @Value("${app.kafka.retry.max-retries:2}") long maxRetries) {
        this.retryBackoffMs = retryBackoffMs;
        this.maxRetries = maxRetries;
    }

    @Bean
    public DeadLetterPublishingRecoverer deadLetterPublishingRecoverer(
            KafkaTemplate<Object, Object> kafkaTemplate) {
        DeadLetterPublishingRecoverer recoverer = new DeadLetterPublishingRecoverer(
                kafkaTemplate,
                (record, exception) -> {
                    String deadLetterTopic = record.topic() + DLT_SUFFIX;
                    log.error(
                            "Kafka record exhausted retries; routing topic={}, partition={}, offset={} to {}",
                            record.topic(), record.partition(), record.offset(), deadLetterTopic, exception);
                    // Let the producer choose a partition so the DLT does not need to mirror
                    // every source topic's partition count.
                    return new TopicPartition(deadLetterTopic, -1);
                });
        recoverer.setFailIfSendResultIsError(true);
        return recoverer;
    }

    @Bean
    public DefaultErrorHandler kafkaErrorHandler(DeadLetterPublishingRecoverer recoverer) {
        DefaultErrorHandler errorHandler = new DefaultErrorHandler(
                recoverer,
                new FixedBackOff(retryBackoffMs, maxRetries));
        errorHandler.setRetryListeners((record, exception, deliveryAttempt) ->
                log.warn(
                        "Kafka listener failure; topic={}, partition={}, offset={}, deliveryAttempt={}",
                        record.topic(), record.partition(), record.offset(), deliveryAttempt, exception));
        return errorHandler;
    }

    @Bean
    public ConcurrentKafkaListenerContainerFactory<Object, Object> kafkaListenerContainerFactory(
            ConcurrentKafkaListenerContainerFactoryConfigurer configurer,
            ConsumerFactory<Object, Object> consumerFactory,
            DefaultErrorHandler errorHandler) {
        ConcurrentKafkaListenerContainerFactory<Object, Object> factory =
                new ConcurrentKafkaListenerContainerFactory<>();
        configurer.configure(factory, consumerFactory);
        factory.setCommonErrorHandler(errorHandler);
        return factory;
    }

    @Bean
    public NewTopics terraOpsDeadLetterTopics() {
        return new NewTopics(
                TopicBuilder.name("action-plans" + DLT_SUFFIX).partitions(1).replicas(1).build(),
                TopicBuilder.name("processed-insights" + DLT_SUFFIX).partitions(1).replicas(1).build(),
                TopicBuilder.name("terra.control.feedback" + DLT_SUFFIX).partitions(1).replicas(1).build());
    }
}
