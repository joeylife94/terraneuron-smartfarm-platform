package com.terraneuron.sense.config;

import com.influxdb.client.InfluxDBClient;
import com.influxdb.client.InfluxDBClientFactory;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

/**
 * InfluxDB 클라이언트 설정
 * 센서 데이터를 시계열 DB에 저장하기 위한 설정
 */
@Slf4j
@Configuration
public class InfluxDbConfig {

    @Value("${influxdb.url}")
    private String url;

    @Value("${influxdb.token}")
    private String token;

    @Value("${influxdb.org}")
    private String org;

    @Value("${influxdb.bucket}")
    private String bucket;

    @Bean
    public InfluxDBClient influxDBClient() {
        try {
            InfluxDBClient client = InfluxDBClientFactory.create(url, token.toCharArray(), org, bucket);
            log.info("✅ InfluxDB 클라이언트 초기화 완료: url={}, org={}, bucket={}", url, org, bucket);
            return client;
        } catch (Exception e) {
            log.error("❌ InfluxDB 클라이언트 초기화 실패: {}", e.getMessage());
            throw e;
        }
    }
}
