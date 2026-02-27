#!/usr/bin/env python3
"""
Terra Data Collector - 통합 테스트 스크립트
실제 공개 API에서 데이터를 수집하고 모든 Exporter 파이프라인을 검증합니다.

테스트 범위:
  1. Open-Meteo 실시간 데이터 수집
  2. Open-Meteo 과거 30일 데이터 수집 (AI 학습용)
  3. NASA POWER 과거 데이터 수집
  4. ThingSpeak 공개 채널 수집
  5. CSV / JSONL / Parquet 내보내기 검증
  6. 내보내기 데이터 품질 검증

성공 기준:
  - 각 Provider에서 최소 10건 이상 수집
  - 전체 수집 500건 이상
  - 모든 Exporter 파일 정상 생성
  - 파인튜닝 JSONL의 instruction/input/output 필드 유효
"""
import asyncio
import json
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

# 프로젝트 루트를 path에 추가
sys.path.insert(0, str(Path(__file__).parent))

from src.config import load_config
from src.collector import Collector
from src.models import CollectedSensorData


# ============ 색상 유틸 ============
class C:
    OK = "\033[92m"
    WARN = "\033[93m"
    FAIL = "\033[91m"
    BOLD = "\033[1m"
    END = "\033[0m"

def ok(msg): print(f"{C.OK}  ✅ {msg}{C.END}")
def warn(msg): print(f"{C.WARN}  ⚠️ {msg}{C.END}")
def fail(msg): print(f"{C.FAIL}  ❌ {msg}{C.END}")
def header(msg): print(f"\n{C.BOLD}{'='*60}\n  {msg}\n{'='*60}{C.END}")
def section(msg): print(f"\n{C.BOLD}--- {msg} ---{C.END}")


# ============ 테스트 결과 추적 ============
results = {"pass": 0, "fail": 0, "warnings": 0, "details": []}

def assert_test(name, condition, detail=""):
    if condition:
        ok(f"[PASS] {name}")
        results["pass"] += 1
        results["details"].append(("PASS", name, detail))
    else:
        fail(f"[FAIL] {name} — {detail}")
        results["fail"] += 1
        results["details"].append(("FAIL", name, detail))


async def test_realtime_collection(collector: Collector):
    """테스트 1: 실시간 데이터 수집"""
    header("TEST 1: 실시간 데이터 수집 (Open-Meteo + ThingSpeak)")

    summary = await collector.collect_and_export(
        provider_names=["open_meteo", "thingspeak"],
        exporter_names=["csv_export", "jsonl_export", "parquet_export"],
        historical=False,
    )

    total = summary.total_records
    print(f"  📊 총 수집 레코드: {total}")
    print(f"  📤 총 내보내기: {summary.total_exported}")
    print(f"  🔌 사용된 Provider: {summary.providers_used}")

    assert_test(
        "Open-Meteo 실시간 수집",
        "open_meteo" in summary.providers_used,
        f"providers: {summary.providers_used}",
    )

    # Open-Meteo는 farm 2개 × 변수 4개 = 최소 8건 예상
    om_result = next((r for r in summary.results if r.provider == "open_meteo"), None)
    if om_result:
        print(f"  🌤️ Open-Meteo: {om_result.records_collected} records, {om_result.duration_ms:.0f}ms")
        assert_test(
            "Open-Meteo 최소 데이터량 (≥4건)",
            om_result.records_collected >= 4,
            f"collected: {om_result.records_collected}",
        )
    else:
        fail("Open-Meteo 결과 없음")
        results["fail"] += 1

    ts_result = next((r for r in summary.results if r.provider == "thingspeak"), None)
    if ts_result:
        print(f"  📡 ThingSpeak: {ts_result.records_collected} records, {ts_result.duration_ms:.0f}ms")
        # ThingSpeak 공개 채널은 가용성이 유동적이므로 warning으로 처리
        if ts_result.records_collected > 0:
            ok(f"ThingSpeak 데이터 수집 성공: {ts_result.records_collected}건")
            results["pass"] += 1
        else:
            warn("ThingSpeak 채널 데이터 없음 (채널 상태에 따라 정상)")
            results["warnings"] += 1
    else:
        warn("ThingSpeak 결과 없음 (공개 채널 의존)")
        results["warnings"] += 1

    assert_test(
        "내보내기 성공",
        summary.total_exported > 0,
        f"exported: {summary.total_exported}",
    )

    return summary.total_records


async def test_historical_collection(collector: Collector):
    """테스트 2: 과거 데이터 수집 (AI 학습용 대량 데이터)"""
    header("TEST 2: 과거 데이터 수집 — AI 학습용 (Open-Meteo 30일)")

    end = (datetime.now(timezone.utc) - timedelta(days=5)).strftime("%Y-%m-%d")
    start = (datetime.now(timezone.utc) - timedelta(days=35)).strftime("%Y-%m-%d")

    print(f"  📅 수집 기간: {start} ~ {end} (30일)")

    summary = await collector.collect_and_export(
        provider_names=["open_meteo"],
        exporter_names=["csv_export", "jsonl_export", "parquet_export"],
        historical=True,
        start_date=start,
        end_date=end,
    )

    total = summary.total_records
    print(f"  📊 총 수집 레코드: {total}")
    print(f"  📤 총 내보내기: {summary.total_exported}")

    # 30일 × 24시간 × 4변수 × 2농장 = 약 5,760건 예상
    assert_test(
        "과거 데이터 대량 수집 (≥500건)",
        total >= 500,
        f"collected: {total} (expected ≥500 for 30 days)",
    )

    assert_test(
        "과거 데이터 내보내기",
        summary.total_exported > 0,
        f"exported: {summary.total_exported}",
    )

    return total


async def test_nasa_power(collector: Collector):
    """테스트 3: NASA POWER 과거 데이터"""
    header("TEST 3: NASA POWER 농업 데이터 수집 (최근 60일)")

    end = (datetime.now(timezone.utc) - timedelta(days=7)).strftime("%Y-%m-%d")
    start = (datetime.now(timezone.utc) - timedelta(days=67)).strftime("%Y-%m-%d")

    print(f"  📅 수집 기간: {start} ~ {end}")

    summary = await collector.collect_and_export(
        provider_names=["nasa_power"],
        exporter_names=["csv_export", "jsonl_export"],
        historical=True,
        start_date=start,
        end_date=end,
    )

    total = summary.total_records
    print(f"  🛰️ NASA POWER: {total} records")

    # NASA POWER는 일 단위, 60일 × 6파라미터 × 2농장 = 약 720건 예상
    assert_test(
        "NASA POWER 수집 (≥100건)",
        total >= 100,
        f"collected: {total}",
    )

    return total


async def test_exported_files():
    """테스트 4: 내보내기 파일 검증"""
    header("TEST 4: 내보내기 파일 품질 검증")

    base = Path(__file__).parent / "data" / "exports"

    # CSV 검증
    section("CSV Files")
    csv_dir = base / "csv"
    csv_files = list(csv_dir.glob("*.csv"))
    print(f"  📁 CSV 파일 수: {len(csv_files)}")
    assert_test("CSV 파일 생성됨", len(csv_files) > 0, f"count: {len(csv_files)}")

    total_csv_rows = 0
    if csv_files:
        import pandas as pd
        for f in csv_files[:3]:  # 처음 3개만 상세 확인
            df = pd.read_csv(f)
            total_csv_rows += len(df)
            print(f"    📄 {f.name}: {len(df)} rows, {list(df.columns)[:6]}...")

        assert_test(
            "CSV 데이터 포함",
            total_csv_rows > 0,
            f"total rows across files: {total_csv_rows}",
        )

        # 컬럼 확인
        sample_df = pd.read_csv(csv_files[0])
        required_cols = {"sensorId", "sensorType", "value", "unit", "farmId", "timestamp"}
        actual_cols = set(sample_df.columns)
        missing = required_cols - actual_cols
        assert_test(
            "CSV 필수 컬럼 존재",
            len(missing) == 0,
            f"missing: {missing}" if missing else f"all present in {actual_cols}",
        )

    # JSONL 검증
    section("JSONL Files (LLM Fine-tuning)")
    jsonl_dir = base / "jsonl"
    jsonl_files = list(jsonl_dir.glob("*.jsonl"))
    print(f"  📁 JSONL 파일 수: {len(jsonl_files)}")
    assert_test("JSONL 파일 생성됨", len(jsonl_files) > 0, f"count: {len(jsonl_files)}")

    if jsonl_files:
        instr_file = jsonl_dir / "finetune_instructions.jsonl"
        if instr_file.exists():
            lines = instr_file.read_text(encoding="utf-8").strip().split("\n")
            print(f"    📝 finetune_instructions.jsonl: {len(lines)} entries")

            # 처음 3개 검증
            valid_count = 0
            for line in lines[:5]:
                entry = json.loads(line)
                has_keys = all(k in entry for k in ["instruction", "input", "output"])
                if has_keys and len(entry["output"]) > 10:
                    valid_count += 1

            assert_test(
                "JSONL instruction 형식 유효",
                valid_count >= 3,
                f"valid entries: {valid_count}/5",
            )

            # 샘플 출력
            sample = json.loads(lines[0])
            print(f"\n    📌 파인튜닝 샘플:")
            print(f"       instruction: {sample['instruction'][:80]}...")
            print(f"       input:       {sample['input']}")
            print(f"       output:      {sample['output'][:100]}...")

        conv_file = jsonl_dir / "finetune_conversations.jsonl"
        if conv_file.exists():
            lines = conv_file.read_text(encoding="utf-8").strip().split("\n")
            print(f"    💬 finetune_conversations.jsonl: {len(lines)} entries")
            assert_test(
                "ShareGPT conversation 형식 생성",
                len(lines) > 0,
                f"entries: {len(lines)}",
            )

    # Parquet 검증
    section("Parquet Files (ML Training)")
    parquet_dir = base / "parquet"
    parquet_files = list(parquet_dir.glob("*.parquet"))
    print(f"  📁 Parquet 파일 수: {len(parquet_files)}")
    assert_test("Parquet 파일 생성됨", len(parquet_files) > 0, f"count: {len(parquet_files)}")

    total_parquet_rows = 0
    if parquet_files:
        import pandas as pd
        for f in parquet_files:
            df = pd.read_parquet(f)
            total_parquet_rows += len(df)
            print(f"    🗂️ {f.name}: {len(df)} rows")

        assert_test(
            "Parquet 데이터 포함",
            total_parquet_rows > 0,
            f"total rows: {total_parquet_rows}",
        )

    return total_csv_rows, total_parquet_rows


async def test_data_quality(collector: Collector):
    """테스트 5: 수집된 데이터 품질 검증"""
    header("TEST 5: 데이터 품질 및 프로젝트 통합 검증")

    # Open-Meteo에서 소량 수집
    records = []
    for name, provider in collector.providers.items():
        if name == "open_meteo":
            records = await provider.collect_all_farms(historical=False)
            break

    if not records:
        warn("데이터 없음, 스킵")
        return

    section("데이터 포맷 검증")

    # terra-sense 페이로드 호환성
    for r in records[:3]:
        payload = r.to_terra_sense_payload()
        required = {"sensorId", "sensorType", "value", "unit", "farmId", "timestamp"}
        assert_test(
            f"terra-sense 페이로드 호환 ({r.sensorType})",
            required.issubset(payload.keys()),
            f"keys: {list(payload.keys())}",
        )
        print(f"    📦 {payload}")

    section("source 태깅 검증 (IoT 구분)")
    for r in records[:2]:
        assert_test(
            f"source='external' 태깅 ({r.sensorType})",
            r.source == "external",
            f"source: {r.source}",
        )
        assert_test(
            f"provider 태깅 ({r.sensorType})",
            r.provider is not None,
            f"provider: {r.provider}",
        )

    section("값 범위 유효성")
    for r in records:
        valid_ranges = {
            "temperature": (-50, 60),
            "humidity": (0, 100),
            "soilMoisture": (0, 100),
            "light": (0, 200000),
        }
        rng = valid_ranges.get(r.sensorType)
        if rng:
            in_range = rng[0] <= r.value <= rng[1]
            assert_test(
                f"값 범위 유효: {r.sensorType}={r.value}{r.unit}",
                in_range,
                f"range: {rng}",
            )

    section("파인튜닝 데이터 생성 검증")
    for r in records[:2]:
        ft = r.to_finetune_instruction()
        print(f"    🧠 {ft['input']} → {ft['output'][:80]}...")
        assert_test(
            f"파인튜닝 output 레이블 생성 ({r.sensorType})",
            len(ft["output"]) > 10,
            f"output length: {len(ft['output'])}",
        )


async def main():
    start_time = time.time()

    print(f"""
{C.BOLD}╔══════════════════════════════════════════════════════════╗
║       🌱 Terra Data Collector Integration Test           ║
║       실제 공개 API 데이터 수집 & 내보내기 테스트          ║
╚══════════════════════════════════════════════════════════╝{C.END}
    """)

    # 설정 로드 & Collector 초기화
    config = load_config()

    # 테스트용: Kafka 비활성화, 파일 Exporter만 활성화
    config.exporters["kafka_bridge"] = {"enabled": False}
    config.exporters["terra_bridge"] = {"enabled": False}

    collector = Collector(config)

    # 기존 내보내기 파일 정리
    export_base = Path(__file__).parent / "data" / "exports"
    for ext in ["csv", "jsonl", "parquet"]:
        d = export_base / ext
        if d.exists():
            for f in d.glob("*"):
                if f.name != ".gitkeep":
                    f.unlink()

    # ============ 테스트 실행 ============
    total_records = 0

    # Test 1: 실시간
    rt_count = await test_realtime_collection(collector)
    total_records += rt_count

    # Test 2: 과거 30일 (대량)
    hist_count = await test_historical_collection(collector)
    total_records += hist_count

    # Test 3: NASA POWER
    nasa_count = await test_nasa_power(collector)
    total_records += nasa_count

    # Test 4: 파일 검증
    csv_rows, parquet_rows = await test_exported_files()

    # Test 5: 데이터 품질
    await test_data_quality(collector)

    # ============ 최종 결과 ============
    elapsed = time.time() - start_time

    header("📊 FINAL TEST RESULTS")
    print(f"""
  총 수집 레코드:     {total_records:,}건
  CSV 내보내기:       {csv_rows:,}행
  Parquet 내보내기:   {parquet_rows:,}행
  소요 시간:          {elapsed:.1f}초

  ✅ PASSED:  {results['pass']}
  ❌ FAILED:  {results['fail']}
  ⚠️ WARNINGS: {results['warnings']}
""")

    if results["fail"] == 0:
        print(f"{C.OK}{C.BOLD}  🎉 ALL TESTS PASSED! 🎉{C.END}")
    else:
        print(f"{C.FAIL}{C.BOLD}  ⚠️ {results['fail']} TEST(S) FAILED{C.END}")
        for status, name, detail in results["details"]:
            if status == "FAIL":
                print(f"    {C.FAIL}✗ {name}: {detail}{C.END}")

    return results["fail"] == 0


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
