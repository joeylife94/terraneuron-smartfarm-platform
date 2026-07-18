-- Local Docker Compose/E2E seed only.
-- Production migrations live in db/migration and never provision demo credentials.

INSERT INTO farms (farm_name, location)
SELECT seed.farm_name, seed.location
FROM (
    SELECT '스마트팜 A동' AS farm_name, '경기도 화성시' AS location
    UNION ALL
    SELECT '스마트팜 B동', '경기도 화성시'
) seed
WHERE NOT EXISTS (
    SELECT 1 FROM farms existing
    WHERE existing.farm_name = seed.farm_name AND existing.location = seed.location
);

INSERT INTO sensors (farm_id, sensor_type, sensor_name, location)
SELECT farm.farm_id, seed.sensor_type, seed.sensor_name, seed.location
FROM (
    SELECT '스마트팜 A동' AS farm_name, 'temperature' AS sensor_type, '온도센서-1' AS sensor_name, 'A동-구역1' AS location
    UNION ALL SELECT '스마트팜 A동', 'humidity', '습도센서-1', 'A동-구역1'
    UNION ALL SELECT '스마트팜 A동', 'co2', 'CO2센서-1', 'A동-구역1'
    UNION ALL SELECT '스마트팜 B동', 'temperature', '온도센서-2', 'B동-구역1'
    UNION ALL SELECT '스마트팜 B동', 'humidity', '습도센서-2', 'B동-구역1'
) seed
JOIN farms farm ON farm.farm_name = seed.farm_name
WHERE NOT EXISTS (
    SELECT 1 FROM sensors existing
    WHERE existing.farm_id = farm.farm_id
      AND existing.sensor_type = seed.sensor_type
      AND existing.sensor_name = seed.sensor_name
);

-- 로컬 Compose/E2E 전용 초기 사용자 데이터 (BCrypt cost 12)
-- 운영 환경에서는 별도 계정 프로비저닝 절차를 사용하고 이 데모 자격증명을 사용하지 않는다.
INSERT IGNORE INTO users (username, password_hash, email, full_name, roles) VALUES
('admin', '$2b$12$VEM9UEYzvq2FvUZeU7o9h.E5HuNxFRnz.arT1lhOtdi6kMFt9ETki', 'admin@terraneuron.io', 'System Admin', 'ROLE_ADMIN,ROLE_OPERATOR'),
('operator', '$2b$12$c42bVxboWHVuXC2UCwUV/evQNPGkcVyCQHtSfGB.DT9j5YExH0byi', 'operator@terraneuron.io', 'Farm Operator', 'ROLE_OPERATOR'),
('viewer', '$2b$12$XEAyS9y2PKe2SM/rqK44ouUaaGaDL.nWYn.JDuHAzj.WySDXrPDpG', 'viewer@terraneuron.io', 'Dashboard Viewer', 'ROLE_VIEWER');

-- 작물 초기 데이터: 한국 스마트팜 주요 작물 5종

-- 1. 토마토
INSERT IGNORE INTO crop_profiles (crop_code, crop_name, crop_name_en, crop_family, description, total_growth_days, difficulty) VALUES
('tomato', '토마토', 'Tomato', '가지과', '한국 스마트팜 대표 작물. 온도와 일조량에 민감하며, 생장 단계별 환경 관리가 중요.', 150, 'MEDIUM');

INSERT IGNORE INTO growth_stages (crop_id, stage_order, stage_code, stage_name, duration_days,
    temp_min, temp_optimal_low, temp_optimal_high, temp_max,
    humidity_min, humidity_optimal_low, humidity_optimal_high, humidity_max,
    co2_min, co2_optimal, co2_max, light_min, light_optimal, light_max,
    soil_moisture_min, soil_moisture_optimal, soil_moisture_max, notes) VALUES
((SELECT id FROM crop_profiles WHERE crop_code='tomato'), 1, 'seeding', '파종/육묘', 25,
    20.0, 23.0, 28.0, 32.0, 60.0, 70.0, 80.0, 90.0, 400, 800, 1200, 300, 500, 800, 60, 70, 80,
    '균일한 온도 유지 필수. 야간 온도 18°C 이상.'),
((SELECT id FROM crop_profiles WHERE crop_code='tomato'), 2, 'vegetative', '영양생장', 30,
    18.0, 22.0, 26.0, 30.0, 55.0, 65.0, 75.0, 85.0, 400, 1000, 1500, 400, 600, 1000, 55, 65, 75,
    '충분한 광량 확보. 질소 시비 중요.'),
((SELECT id FROM crop_profiles WHERE crop_code='tomato'), 3, 'flowering', '개화기', 20,
    16.0, 20.0, 25.0, 28.0, 50.0, 60.0, 70.0, 80.0, 400, 1000, 1500, 500, 700, 1000, 50, 60, 70,
    '과도한 습도는 수분 불량 유발. 야간 15-17°C 유지.'),
((SELECT id FROM crop_profiles WHERE crop_code='tomato'), 4, 'fruiting', '착과/비대기', 50,
    15.0, 20.0, 26.0, 30.0, 50.0, 60.0, 70.0, 80.0, 400, 1000, 1500, 500, 700, 1000, 50, 65, 75,
    '칼륨 시비 강화. 일교차 8-10°C로 착색 촉진.'),
((SELECT id FROM crop_profiles WHERE crop_code='tomato'), 5, 'harvest', '수확기', 25,
    14.0, 18.0, 24.0, 28.0, 50.0, 55.0, 65.0, 75.0, 300, 600, 1000, 400, 600, 800, 45, 55, 65,
    '과숙 방지를 위해 온도 관리. 수확 후 낮은 습도 유지.');

-- 2. 딸기
INSERT IGNORE INTO crop_profiles (crop_code, crop_name, crop_name_en, crop_family, description, total_growth_days, difficulty) VALUES
('strawberry', '딸기', 'Strawberry', '장미과', '고부가가치 작물. 일장과 온도에 의한 화아분화 관리가 핵심.', 180, 'HARD');

INSERT IGNORE INTO growth_stages (crop_id, stage_order, stage_code, stage_name, duration_days,
    temp_min, temp_optimal_low, temp_optimal_high, temp_max,
    humidity_min, humidity_optimal_low, humidity_optimal_high, humidity_max,
    co2_min, co2_optimal, co2_max, light_min, light_optimal, light_max,
    soil_moisture_min, soil_moisture_optimal, soil_moisture_max, notes) VALUES
((SELECT id FROM crop_profiles WHERE crop_code='strawberry'), 1, 'planting', '정식기', 20,
    15.0, 18.0, 23.0, 28.0, 60.0, 70.0, 80.0, 90.0, 300, 600, 1000, 200, 400, 600, 60, 70, 80,
    '활착 기간 충분한 수분 공급. 차광 관리.'),
((SELECT id FROM crop_profiles WHERE crop_code='strawberry'), 2, 'vegetative', '영양생장', 40,
    12.0, 15.0, 20.0, 25.0, 55.0, 65.0, 75.0, 85.0, 300, 800, 1200, 300, 500, 800, 55, 65, 75,
    '화아분화 유도를 위해 야간 온도 관리.'),
((SELECT id FROM crop_profiles WHERE crop_code='strawberry'), 3, 'flowering', '개화기', 30,
    8.0, 12.0, 18.0, 22.0, 50.0, 55.0, 65.0, 75.0, 400, 1000, 1500, 400, 600, 1000, 50, 60, 70,
    '수분 매개 관리. 과습 방지 중요.'),
((SELECT id FROM crop_profiles WHERE crop_code='strawberry'), 4, 'fruiting', '착과/비대기', 60,
    8.0, 13.0, 20.0, 25.0, 50.0, 55.0, 65.0, 75.0, 400, 1000, 1500, 500, 700, 1000, 45, 55, 65,
    '당도 향상을 위해 일교차 관리. 칼슘 시비.'),
((SELECT id FROM crop_profiles WHERE crop_code='strawberry'), 5, 'harvest', '수확기', 30,
    5.0, 10.0, 18.0, 23.0, 45.0, 50.0, 60.0, 70.0, 300, 600, 1000, 400, 600, 800, 40, 50, 60,
    '잿빛곰팡이 주의. 수확 후 저온 보관.');

-- 3. 상추
INSERT IGNORE INTO crop_profiles (crop_code, crop_name, crop_name_en, crop_family, description, total_growth_days, difficulty) VALUES
('lettuce', '상추', 'Lettuce', '국화과', '빠른 생육 주기의 엽채류. 고온에서 추대하므로 온도 관리 핵심.', 45, 'EASY');

INSERT IGNORE INTO growth_stages (crop_id, stage_order, stage_code, stage_name, duration_days,
    temp_min, temp_optimal_low, temp_optimal_high, temp_max,
    humidity_min, humidity_optimal_low, humidity_optimal_high, humidity_max,
    co2_min, co2_optimal, co2_max, light_min, light_optimal, light_max,
    soil_moisture_min, soil_moisture_optimal, soil_moisture_max, notes) VALUES
((SELECT id FROM crop_profiles WHERE crop_code='lettuce'), 1, 'seeding', '파종/육묘', 10,
    15.0, 18.0, 22.0, 25.0, 65.0, 70.0, 80.0, 90.0, 300, 600, 1000, 200, 400, 600, 65, 75, 85,
    '발아 적온 18-20°C. 광발아 종자.'),
((SELECT id FROM crop_profiles WHERE crop_code='lettuce'), 2, 'vegetative', '본엽 생장', 25,
    10.0, 15.0, 20.0, 25.0, 55.0, 60.0, 70.0, 80.0, 400, 800, 1200, 300, 500, 800, 55, 65, 75,
    '25°C 이상 고온 시 추대 위험. 차광 필요할 수 있음.'),
((SELECT id FROM crop_profiles WHERE crop_code='lettuce'), 3, 'harvest', '수확기', 10,
    10.0, 15.0, 20.0, 24.0, 50.0, 55.0, 65.0, 75.0, 300, 600, 1000, 300, 500, 700, 50, 60, 70,
    '수확 2-3일 전 관수 줄여 저장성 향상.');

-- 4. 오이
INSERT IGNORE INTO crop_profiles (crop_code, crop_name, crop_name_en, crop_family, description, total_growth_days, difficulty) VALUES
('cucumber', '오이', 'Cucumber', '박과', '고온성 작물로 자람이 빠름. 과습에 강하지만 과건에 약함.', 90, 'MEDIUM');

INSERT IGNORE INTO growth_stages (crop_id, stage_order, stage_code, stage_name, duration_days,
    temp_min, temp_optimal_low, temp_optimal_high, temp_max,
    humidity_min, humidity_optimal_low, humidity_optimal_high, humidity_max,
    co2_min, co2_optimal, co2_max, light_min, light_optimal, light_max,
    soil_moisture_min, soil_moisture_optimal, soil_moisture_max, notes) VALUES
((SELECT id FROM crop_profiles WHERE crop_code='cucumber'), 1, 'seeding', '파종/육묘', 15,
    22.0, 25.0, 28.0, 32.0, 65.0, 75.0, 85.0, 95.0, 300, 600, 1000, 200, 400, 700, 65, 75, 85,
    '발아 적온 25-28°C. 고온 필수.'),
((SELECT id FROM crop_profiles WHERE crop_code='cucumber'), 2, 'vegetative', '덩굴 생장', 25,
    18.0, 22.0, 28.0, 32.0, 60.0, 70.0, 80.0, 90.0, 400, 1000, 1500, 400, 600, 1000, 60, 70, 80,
    '충분한 수분과 질소 공급. 유인 작업.'),
((SELECT id FROM crop_profiles WHERE crop_code='cucumber'), 3, 'flowering', '개화/착과', 15,
    16.0, 20.0, 26.0, 30.0, 55.0, 65.0, 75.0, 85.0, 400, 1000, 1500, 500, 700, 1000, 55, 65, 75,
    '주간/야간 온도차 관리. 암꽃 착생 촉진.'),
((SELECT id FROM crop_profiles WHERE crop_code='cucumber'), 4, 'harvest', '수확기', 35,
    15.0, 20.0, 26.0, 30.0, 55.0, 60.0, 70.0, 80.0, 400, 800, 1200, 400, 600, 800, 55, 65, 75,
    '연속 수확 기간. 적엽/적과로 수세 유지.');

-- 5. 파프리카
INSERT IGNORE INTO crop_profiles (crop_code, crop_name, crop_name_en, crop_family, description, total_growth_days, difficulty) VALUES
('paprika', '파프리카', 'Paprika (Bell Pepper)', '가지과', '고부가가치 수출 작물. 정밀 환경제어 필요.', 180, 'HARD');

INSERT IGNORE INTO growth_stages (crop_id, stage_order, stage_code, stage_name, duration_days,
    temp_min, temp_optimal_low, temp_optimal_high, temp_max,
    humidity_min, humidity_optimal_low, humidity_optimal_high, humidity_max,
    co2_min, co2_optimal, co2_max, light_min, light_optimal, light_max,
    soil_moisture_min, soil_moisture_optimal, soil_moisture_max, notes) VALUES
((SELECT id FROM crop_profiles WHERE crop_code='paprika'), 1, 'seeding', '파종/육묘', 30,
    22.0, 25.0, 28.0, 32.0, 65.0, 70.0, 80.0, 90.0, 400, 800, 1200, 300, 500, 800, 60, 70, 80,
    '발아 적온 25-30°C. 야간 20°C 이상 유지.'),
((SELECT id FROM crop_profiles WHERE crop_code='paprika'), 2, 'vegetative', '영양생장', 40,
    18.0, 22.0, 26.0, 30.0, 55.0, 65.0, 75.0, 85.0, 400, 1000, 1500, 500, 700, 1000, 55, 65, 75,
    '강한 줄기 형성을 위한 광량/CO2 관리.'),
((SELECT id FROM crop_profiles WHERE crop_code='paprika'), 3, 'flowering', '개화기', 25,
    16.0, 20.0, 25.0, 28.0, 50.0, 60.0, 70.0, 80.0, 400, 1000, 1500, 600, 800, 1200, 50, 60, 70,
    '야간 16-18°C로 화아분화 촉진. 붕소 엽면시비.'),
((SELECT id FROM crop_profiles WHERE crop_code='paprika'), 4, 'fruiting', '착과/비대기', 55,
    16.0, 20.0, 26.0, 30.0, 50.0, 60.0, 70.0, 80.0, 400, 1000, 1500, 600, 800, 1200, 50, 60, 70,
    '칼슘/칼륨 시비 강화. 열과 방지 환기.'),
((SELECT id FROM crop_profiles WHERE crop_code='paprika'), 5, 'harvest', '수확/착색기', 30,
    14.0, 18.0, 24.0, 28.0, 45.0, 55.0, 65.0, 75.0, 300, 600, 1000, 500, 700, 1000, 45, 55, 65,
    '착색을 위해 일교차 10°C 이상 확보.');

-- 데모 농장-작물 매핑
INSERT INTO farm_crops (farm_id, crop_id, zone, planted_at, current_stage_order, expected_harvest, status)
SELECT seed.farm_id, crop.id, seed.zone, seed.planted_at, seed.stage_order, seed.expected_harvest, 'GROWING'
FROM (
    SELECT 'farm-A' AS farm_id, 'tomato' AS crop_code, 'zone-A' AS zone,
           DATE '2026-01-15' AS planted_at, 3 AS stage_order, DATE '2026-06-15' AS expected_harvest
    UNION ALL SELECT 'farm-A', 'lettuce', 'zone-B', DATE '2026-02-10', 2, DATE '2026-03-27'
    UNION ALL SELECT 'farm-B', 'strawberry', 'zone-A', DATE '2025-10-01', 4, DATE '2026-03-30'
) seed
JOIN crop_profiles crop ON crop.crop_code = seed.crop_code
WHERE NOT EXISTS (
    SELECT 1 FROM farm_crops existing
    WHERE existing.farm_id = seed.farm_id
      AND existing.crop_id = crop.id
      AND existing.zone = seed.zone
      AND existing.planted_at = seed.planted_at
);
