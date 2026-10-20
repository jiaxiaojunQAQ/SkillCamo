"""Unified Skill Scanner command-line entrypoint."""

from __future__ import annotations

from pathlib import Path

import click

from .entry import run_from_config


@click.command()
@click.option("-c", "--config", "config_path", default="./config/main.yaml", help="配置文件路径 (默认: ./config/main.yaml)")
@click.option("--dry-run", is_flag=True, help="显示执行计划但不实际运行")
@click.option("--force", "force_rerun", is_flag=True, help="删除 state.json 强制重新执行")
@click.version_option(version="1.0.0")
@click.argument("target", required=False)
def cli(config_path: str, dry_run: bool, force_rerun: bool, target: str | None) -> None:
    """Unified Skill Scanner — 配置驱动的技能安全扫描入口。"""
    target_path = Path(target) if target else None
    if target_path is not None and not target_path.exists():
        raise click.ClickException(f"Target path does not exist: {target_path}")

    run_from_config(
        config_path=Path(config_path),
        target=target_path,
        dry_run=dry_run,
        force_rerun=force_rerun,
    )


def main() -> None:
    cli()


if __name__ == "__main__":
    main()
