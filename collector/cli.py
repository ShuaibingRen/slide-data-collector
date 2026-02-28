"""CLI entry point for slide-data-collector."""

import os
import sys
from pathlib import Path

import click
import yaml


def _load_config():
    """Load config.yaml from the current directory or COLLECTOR_CONFIG env."""
    config_path = os.environ.get("COLLECTOR_CONFIG", "config.yaml")
    if not os.path.exists(config_path):
        return {}
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _resolve_schemas_dir(config: dict) -> str:
    """Resolve the schemas directory path."""
    schemas_dir = config.get("schemas", {}).get("directory", "./schemas")
    if not os.path.isabs(schemas_dir):
        schemas_dir = os.path.join(os.getcwd(), schemas_dir)
    return schemas_dir


CONTEXT_SETTINGS = dict(help_option_names=["--help", "-h"])
VALID_TYPES = ["sample", "slide", "imaging", "all"]


@click.group(context_settings=CONTEXT_SETTINGS)
@click.version_option(version="0.1.0")
def main():
    """slide-data-collector: A lightweight (meta)data collection CLI.

    临床切片成像元数据收集工具。
    """
    pass


# ============================================================
# template commands
# ============================================================

@main.group()
def template():
    """Generate Excel metadata templates / 生成 Excel 元数据模板"""
    pass


@template.command("gen")
@click.option(
    "-t", "--type", "data_type",
    required=True,
    type=click.Choice(VALID_TYPES, case_sensitive=False),
    help="Template type: sample, slide, imaging, or all",
)
@click.option(
    "-o", "--output", "output_dir",
    default="./output",
    help="Output directory (default: ./output)",
)
def template_gen(data_type, output_dir):
    """Generate empty Excel template(s) with data validation.

    生成带有数据验证的空 Excel 模板。
    """
    from collector.excel import generate_template, generate_all_templates

    config = _load_config()
    schemas_dir = _resolve_schemas_dir(config)

    if data_type == "all":
        files = generate_all_templates(schemas_dir, output_dir)
        click.echo(f"✅ Generated {len(files)} template(s) / 已生成 {len(files)} 个模板:")
        for f in files:
            click.echo(f"  📄 {f}")
    else:
        schema_path = os.path.join(schemas_dir, f"{data_type}.yaml")
        if not os.path.exists(schema_path):
            click.echo(f"❌ Schema not found: {schema_path}", err=True)
            sys.exit(1)
        output_path = os.path.join(output_dir, f"{data_type}_manifest.xlsx")
        generate_template(schema_path, output_path)
        click.echo(f"✅ Generated template / 已生成模板: {output_path}")


# ============================================================
# validate command
# ============================================================

@main.command("validate")
@click.argument("manifest_path", type=click.Path(exists=True))
@click.option(
    "-t", "--type", "data_type",
    type=click.Choice(["sample", "slide", "imaging"], case_sensitive=False),
    default=None,
    help="Schema type. Auto-detected from filename if not specified.",
)
def validate_cmd(manifest_path, data_type):
    """Validate a filled-in manifest against its schema.

    验证已填写的元数据清单。

    MANIFEST_PATH: Path to the filled .xlsx or .csv file.
    """
    from collector.validator import validate_manifest, format_errors

    config = _load_config()
    schemas_dir = _resolve_schemas_dir(config)

    # Auto-detect type from filename if not specified
    if data_type is None:
        basename = Path(manifest_path).stem.lower()
        for t in ["sample", "slide", "imaging"]:
            if t in basename:
                data_type = t
                break
        if data_type is None:
            click.echo(
                "❌ Cannot auto-detect type from filename. "
                "Use --type to specify. / 无法从文件名自动检测类型，请使用 --type 指定",
                err=True,
            )
            sys.exit(1)

    schema_path = os.path.join(schemas_dir, f"{data_type}.yaml")
    if not os.path.exists(schema_path):
        click.echo(f"❌ Schema not found: {schema_path}", err=True)
        sys.exit(1)

    errors = validate_manifest(manifest_path, schema_path)
    click.echo(format_errors(errors))

    if errors:
        sys.exit(1)


# ============================================================
# s3 commands
# ============================================================

@main.group()
def s3():
    """S3 bucket operations / S3 桶操作"""
    pass


@s3.command("scan")
@click.option("-b", "--bucket", required=True, help="S3 bucket name")
@click.option("-p", "--prefix", default="", help="S3 key prefix (folder)")
def s3_scan(bucket, prefix):
    """Scan and list files in an S3 bucket.

    扫描并列出 S3 桶中的文件。
    """
    from collector.s3 import scan_bucket

    objects = scan_bucket(bucket, prefix)
    click.echo(f"📦 Found {len(objects)} file(s) in s3://{bucket}/{prefix}\n")
    for obj in objects[:50]:
        size_mb = obj["size_bytes"] / (1024 * 1024)
        click.echo(f"  {obj['key']}  ({size_mb:.1f} MB)")
    if len(objects) > 50:
        click.echo(f"\n  ... and {len(objects) - 50} more files")


@s3.command("check")
@click.argument("manifest_path", type=click.Path(exists=True))
@click.option("-b", "--bucket", default=None, help="S3 bucket name (auto-detected from s3_path if omitted)")
def s3_check(manifest_path, bucket):
    """Check manifest s3_path entries against actual S3 contents.

    检查清单中的 S3 路径是否真实存在。

    MANIFEST_PATH: Path to the imaging manifest file.
    """
    from collector.s3 import check_manifest_against_s3, format_s3_check_result

    found, missing, extra = check_manifest_against_s3(manifest_path, bucket)
    click.echo(format_s3_check_result(found, missing, extra))

    if missing:
        sys.exit(1)


# ============================================================
# report command
# ============================================================

@main.command("report")
@click.option("--sample", "sample_path", required=True, type=click.Path(exists=True),
              help="Path to filled sample manifest")
@click.option("--slide", "slide_path", required=True, type=click.Path(exists=True),
              help="Path to filled slide manifest")
@click.option("--imaging", "imaging_path", required=True, type=click.Path(exists=True),
              help="Path to filled imaging manifest")
@click.option("-o", "--output", "output_path", default="./output/delivery_report.xlsx",
              help="Output report path")
def report_cmd(sample_path, slide_path, imaging_path, output_path):
    """Generate a merged delivery report from all manifests.

    从三份清单生成合并交付报告。
    """
    from collector.report import generate_report, format_report_summary

    generate_report(sample_path, slide_path, imaging_path, output_path)
    click.echo(format_report_summary(output_path))


if __name__ == "__main__":
    main()
