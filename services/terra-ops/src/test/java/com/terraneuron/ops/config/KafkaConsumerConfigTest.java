package com.terraneuron.ops.config;

import org.apache.kafka.clients.consumer.Consumer;
import org.apache.kafka.clients.consumer.ConsumerRecord;
import org.apache.kafka.clients.admin.NewTopic;
import org.apache.kafka.clients.producer.ProducerRecord;
import org.junit.jupiter.api.Test;
import org.springframework.boot.autoconfigure.kafka.ConcurrentKafkaListenerContainerFactoryConfigurer;
import org.springframework.kafka.config.ConcurrentKafkaListenerContainerFactory;
import org.springframework.kafka.core.ConsumerFactory;
import org.springframework.kafka.core.KafkaTemplate;
import org.springframework.kafka.listener.DeadLetterPublishingRecoverer;
import org.springframework.kafka.listener.DefaultErrorHandler;
import org.springframework.kafka.listener.MessageListenerContainer;
import org.springframework.kafka.support.SendResult;
import org.springframework.test.util.ReflectionTestUtils;

import java.util.concurrent.CompletableFuture;
import java.util.Collection;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.same;
import static org.mockito.Mockito.times;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

class KafkaConsumerConfigTest {

    @Test
    @SuppressWarnings("unchecked")
    void allConsumedTopicsHaveDeclaredDltTopics() {
        KafkaConsumerConfig config = new KafkaConsumerConfig(0, 2);

        Collection<NewTopic> topics = ReflectionTestUtils.invokeMethod(
                config.terraOpsDeadLetterTopics(), "getNewTopics");

        assertThat(topics)
                .extracting(NewTopic::name)
                .containsExactlyInAnyOrder(
                        "action-plans.DLT",
                        "processed-insights.DLT",
                        "terra.control.feedback.DLT");
    }

    @Test
    @SuppressWarnings({"unchecked", "rawtypes"})
    void exhaustedRecordIsPublishedToDeterministicDltTopic() {
        KafkaConsumerConfig config = new KafkaConsumerConfig(0, 2);
        KafkaTemplate<Object, Object> kafkaTemplate = mock(KafkaTemplate.class);
        SendResult<Object, Object> sendResult = mock(SendResult.class);
        when(kafkaTemplate.send(any(ProducerRecord.class)))
                .thenReturn(CompletableFuture.completedFuture(sendResult));

        DeadLetterPublishingRecoverer recoverer = config.deadLetterPublishingRecoverer(kafkaTemplate);
        ConsumerRecord<String, Object> failedRecord =
                new ConsumerRecord<>("processed-insights", 2, 17L, "farm-1", "invalid");

        recoverer.accept(failedRecord, null, new IllegalStateException("database unavailable"));

        var recordCaptor = org.mockito.ArgumentCaptor.forClass(ProducerRecord.class);
        verify(kafkaTemplate).send(recordCaptor.capture());
        ProducerRecord<?, ?> deadLetterRecord = recordCaptor.getValue();
        assertThat(deadLetterRecord.topic()).isEqualTo("processed-insights.DLT");
        assertThat(deadLetterRecord.partition()).isNull();
        assertThat(deadLetterRecord.key()).isEqualTo("farm-1");
        assertThat(deadLetterRecord.value()).isEqualTo("invalid");
    }

    @Test
    void errorHandlerRetriesTwiceBeforeRecovery() {
        KafkaConsumerConfig config = new KafkaConsumerConfig(0, 2);
        DeadLetterPublishingRecoverer recoverer = mock(DeadLetterPublishingRecoverer.class);
        DefaultErrorHandler errorHandler = config.kafkaErrorHandler(recoverer);
        ConsumerRecord<String, String> failedRecord =
                new ConsumerRecord<>("action-plans", 0, 8L, "farm-1", "invalid");
        @SuppressWarnings("unchecked")
        Consumer<Object, Object> consumer = mock(Consumer.class);
        MessageListenerContainer container = mock(MessageListenerContainer.class);
        IllegalStateException failure = new IllegalStateException("persistence failed");

        assertThat(errorHandler.handleOne(failure, failedRecord, consumer, container)).isFalse();
        assertThat(errorHandler.handleOne(failure, failedRecord, consumer, container)).isFalse();
        assertThat(errorHandler.handleOne(failure, failedRecord, consumer, container)).isTrue();

        verify(recoverer, times(1)).accept(same(failedRecord), same(consumer), same(failure));
    }

    @Test
    void listenerContainerFactoryUsesConfiguredErrorHandler() {
        KafkaConsumerConfig config = new KafkaConsumerConfig(0, 2);
        ConcurrentKafkaListenerContainerFactoryConfigurer configurer =
                mock(ConcurrentKafkaListenerContainerFactoryConfigurer.class);
        @SuppressWarnings("unchecked")
        ConsumerFactory<Object, Object> consumerFactory = mock(ConsumerFactory.class);
        DefaultErrorHandler errorHandler = mock(DefaultErrorHandler.class);

        ConcurrentKafkaListenerContainerFactory<Object, Object> factory =
                config.kafkaListenerContainerFactory(configurer, consumerFactory, errorHandler);

        verify(configurer).configure(factory, consumerFactory);
        assertThat(ReflectionTestUtils.getField(factory, "commonErrorHandler"))
                .isSameAs(errorHandler);
    }
}
