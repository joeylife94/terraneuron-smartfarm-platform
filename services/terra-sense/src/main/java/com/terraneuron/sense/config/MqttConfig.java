package com.terraneuron.sense.config;

import lombok.extern.slf4j.Slf4j;
import org.eclipse.paho.client.mqttv3.MqttClient;
import org.eclipse.paho.client.mqttv3.MqttConnectOptions;
import org.eclipse.paho.client.mqttv3.MqttException;
import org.eclipse.paho.client.mqttv3.persist.MemoryPersistence;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

/**
 * MQTT 클라이언트 설정
 * Eclipse Paho를 이용한 Mosquitto 브로커 연결
 *
 * 역할:
 * 1) 센서 → MQTT 토픽 구독 (Inbound)
 * 2) 제어 명령 → MQTT 디바이스 토픽 발행 (Outbound)
 */
@Slf4j
@Configuration
public class MqttConfig {

    @Value("${mqtt.broker.url:tcp://localhost:1883}")
    private String brokerUrl;

    @Value("${mqtt.client.id:terra-sense-bridge}")
    private String clientId;

    @Value("${mqtt.connect.timeout:10}")
    private int connectTimeout;

    @Value("${mqtt.keepalive:60}")
    private int keepAlive;

    @Value("${mqtt.auto-reconnect:true}")
    private boolean autoReconnect;

    @Bean(destroyMethod = "disconnect")
    public MqttClient mqttClient() throws MqttException {
        log.info("🔌 MQTT 클라이언트 초기화: broker={}, clientId={}", brokerUrl, clientId);

        MqttConnectOptions options = new MqttConnectOptions();
        options.setServerURIs(new String[]{brokerUrl});
        options.setConnectionTimeout(connectTimeout);
        options.setKeepAliveInterval(keepAlive);
        options.setAutomaticReconnect(autoReconnect);
        options.setCleanSession(true);
        // 최대 재전송 중 메시지 수
        options.setMaxInflight(50);

        MqttClient client = new MqttClient(brokerUrl, clientId, new MemoryPersistence());
        client.connect(options);

        log.info("✅ MQTT 브로커 연결 완료: {}", brokerUrl);
        return client;
    }
}
