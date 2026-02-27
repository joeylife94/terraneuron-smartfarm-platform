#!/usr/bin/env python3
"""
Terra Data Collector - Standalone CLI
서비스 없이 독립적으로 데이터 수집/내보내기 실행

Usage:
    # 실시간 데이터 수집 → terra-sense 전송
    python -m src.cli collect --provider open_meteo --exporter terra_bridge

    # 과거 데이터 수집 → CSV 내보내기 (AI 학습용)
    python -m src.cli collect --provider open_meteo --historical --start 2024-01-01 --end 2025-01-01 --exporter csv_export

    # 전체 Provider에서 수집 → 전체 Exporter로 내보내기
    python -m src.cli collect --all

    # 과거 데이터 수집 → JSONL 파인튜닝 데이터 생성
    python -m src.cli collect --provider nasa_power --historical --exporter jsonl_export

    # 상태 확인
    python -m src.cli status

    # Provider 목록 확인
    python -m src.cli providers
"""
import asyncio
import sys
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

# 프로젝트 루트를 path에 추가
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import load_config
from src.collector import Collector

console = Console()


@click.group()
@click.option("--config", "-c", default=None, help="설정 파일 경로")
@click.pass_context
def cli(ctx, config):
    """🌱 Terra Data Collector CLI — 외부 농업 데이터 수집 도구"""
    ctx.ensure_object(dict)
    ctx.obj["config_path"] = config


@cli.command()
@click.option("--provider", "-p", multiple=True, help="사용할 Provider (여러 개 가능)")
@click.option("--exporter", "-e", multiple=True, help="사용할 Exporter (여러 개 가능)")
@click.option("--historical", "-H", is_flag=True, help="과거 데이터 수집")
@click.option("--start", "-s", default=None, help="시작일 (YYYY-MM-DD)")
@click.option("--end", "-E", default=None, help="종료일 (YYYY-MM-DD)")
@click.option("--all", "-a", "use_all", is_flag=True, help="전체 Provider/Exporter 사용")
@click.pass_context
def collect(ctx, provider, exporter, historical, start, end, use_all):
    """데이터 수집 실행"""
    config = load_config(ctx.obj["config_path"])
    collector = Collector(config)

    provider_names = list(provider) if provider and not use_all else None
    exporter_names = list(exporter) if exporter and not use_all else None

    mode = "📜 Historical" if historical else "⚡ Realtime"
    console.print(Panel(
        f"[bold green]{mode} Data Collection[/bold green]\n"
        f"Providers: {provider_names or 'ALL'}\n"
        f"Exporters: {exporter_names or 'ALL'}\n"
        + (f"Period: {start or 'auto'} ~ {end or 'auto'}" if historical else ""),
        title="🌱 Terra Data Collector",
    ))

    async def run():
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Collecting data...", total=None)

            summary = await collector.collect_and_export(
                provider_names=provider_names,
                exporter_names=exporter_names,
                historical=historical,
                start_date=start,
                end_date=end,
            )

            progress.update(task, description="Complete!")

        # 결과 테이블
        table = Table(title="📊 Collection Summary")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="green")

        table.add_row("Session ID", summary.session_id)
        table.add_row("Records Collected", str(summary.total_records))
        table.add_row("Records Exported", str(summary.total_exported))
        table.add_row("Errors", str(summary.total_errors))
        table.add_row("Providers Used", ", ".join(summary.providers_used))

        console.print(table)

        # 개별 결과
        if summary.results:
            detail_table = Table(title="📋 Provider Details")
            detail_table.add_column("Provider")
            detail_table.add_column("Records")
            detail_table.add_column("Duration (ms)")
            detail_table.add_column("Errors")

            for r in summary.results:
                detail_table.add_row(
                    r.provider,
                    str(r.records_collected),
                    f"{r.duration_ms:.0f}",
                    str(len(r.errors)) if r.errors else "0",
                )
            console.print(detail_table)

        if summary.total_errors > 0:
            console.print(f"[yellow]⚠️ {summary.total_errors} errors occurred[/yellow]")
        else:
            console.print("[green]✅ All operations completed successfully![/green]")

    asyncio.run(run())


@cli.command()
@click.pass_context
def providers(ctx):
    """Provider 목록 표시"""
    config = load_config(ctx.obj["config_path"])

    table = Table(title="🔌 Data Providers")
    table.add_column("Provider", style="cyan")
    table.add_column("Status", style="green")
    table.add_column("Quality")
    table.add_column("Description")

    provider_info = {
        "open_meteo": ("🌤️ Open-Meteo", "고품질 기상 데이터 (ECMWF 기반)"),
        "nasa_power": ("🛰️ NASA POWER", "농업 특화 기상 데이터 (30년+)"),
        "thingspeak": ("📡 ThingSpeak", "실제 IoT 센서 공개 채널 데이터"),
    }

    for name, pconfig in config.providers.items():
        enabled = pconfig.get("enabled", False)
        info = provider_info.get(name, (name, ""))
        table.add_row(
            info[0],
            "✅ Enabled" if enabled else "❌ Disabled",
            "HIGH" if name != "thingspeak" else "MEDIUM",
            info[1],
        )

    console.print(table)


@cli.command()
@click.pass_context
def exporters(ctx):
    """Exporter 목록 표시"""
    config = load_config(ctx.obj["config_path"])

    table = Table(title="📤 Data Exporters")
    table.add_column("Exporter", style="cyan")
    table.add_column("Status", style="green")
    table.add_column("Description")

    exporter_info = {
        "terra_bridge": ("🌉 Terra Bridge", "terra-sense HTTP API로 전송 (파이프라인 테스트)"),
        "kafka_bridge": ("📨 Kafka Bridge", "raw-sensor-data 토픽 직접 전송"),
        "csv_export": ("📊 CSV Export", "AI 학습용 CSV 데이터셋"),
        "jsonl_export": ("📝 JSONL Export", "LLM 파인튜닝용 Instruction 데이터"),
        "parquet_export": ("🗂️ Parquet Export", "대규모 ML 학습용 컬럼 스토리지"),
    }

    for name, econfig in config.exporters.items():
        enabled = econfig.get("enabled", False)
        info = exporter_info.get(name, (name, ""))
        table.add_row(
            info[0],
            "✅ Enabled" if enabled else "❌ Disabled",
            info[1],
        )

    console.print(table)


@cli.command()
@click.pass_context
def status(ctx):
    """전체 상태 확인"""
    config = load_config(ctx.obj["config_path"])

    console.print(Panel(
        "[bold green]Terra Data Collector v1.0.0[/bold green]\n\n"
        f"Farms configured: {len(config.farms)}\n"
        f"Providers: {sum(1 for p in config.providers.values() if p.get('enabled'))}"
        f" / {len(config.providers)}\n"
        f"Exporters: {sum(1 for e in config.exporters.values() if e.get('enabled'))}"
        f" / {len(config.exporters)}\n"
        f"Scheduler: {'✅ Enabled' if config.scheduler.get('enabled') else '❌ Disabled'}",
        title="🌱 Status",
    ))


if __name__ == "__main__":
    cli()
