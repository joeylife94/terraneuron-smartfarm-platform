package com.terraneuron.sense.service;

import com.influxdb.client.InfluxDBClient;
import com.influxdb.client.WriteApiBlocking;
import com.influxdb.client.domain.WritePrecision;
import com.influxdb.client.write.Point;
import com.terraneuron.sense.model.SensorData;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

import java.time.Instant;

/**
 * InfluxDB 시계열 저장 서비스
 * 센서 데이터를 InfluxDB에 영속화하여 추세 분석/이력 조회를 지원
 * 
 * 저장 스키마:
 *   measurement: "sensor_data"
 *   tags: farmId, sensorId, sensorType, unit
 *   fields: value
 *   timestamp: 센서 타임스탬프 (또는 수신 시점)
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class InfluxDbWriterService {

    private final InfluxDBClient influxDBClient;

    @Value("${influxdb.bucket}")
    private String bucket;

    @Value("${influxdb.org}")
    private String org;

    /**
     * 센서 데이터를 InfluxDB에 저장
     * 실패 시 로그만 남기고 Kafka 전송은 영향받지 않음 (fire-and-forget)
     */
    public void writeSensorData(SensorData sensorData) {
        try {
            WriteApiBlocking writeApi = influxDBClient.getWriteApiBlocking();

            Instant timestamp = sensorData.getTimestamp() != null 
                    ? sensorData.getTimestamp() 
                    : Instant.now();

            Point point = Point.measurement("sensor_data")
                    .addTag("farmId", sensorData.getFarmId())
                    .addTag("sensorId", sensorData.getSensorId())
                    .addTag("sensorType", sensorData.getSensorType())
                    .addTag("unit", sensorData.getUnit() != null ? sensorData.getUnit() : "unknown")
                    .addField("value", sensorData.getValue())
                    .time(timestamp, WritePrecision.MS);

            writeApi.writePoint(bucket, org, point);

            log.debug("✅ InfluxDB 저장 완료: sensorId={}, type={}, value={}", 
                    sensorData.getSensorId(), 
                    sensorData.getSensorType(), 
                    sensorData.getValue());

        } catch (Exception e) {
            // InfluxDB 장애가 Kafka 파이프라인을 중단시키지 않도록 로그만 남김
            log.warn("⚠️ InfluxDB 저장 실패 (Kafka 전송은 정상 진행): sensorId={}, error={}", 
                    sensorData.getSensorId(), e.getMessage());
        }
    }
}
