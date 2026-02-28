"""S3 utilities: scan buckets and check manifest against S3 contents."""

import os
from typing import List, Tuple
from urllib.parse import urlparse

import pandas as pd

try:
    import boto3
    from botocore.exceptions import ClientError, NoCredentialsError
except ImportError:
    boto3 = None


def get_s3_client():
    """Create an S3 client using environment variable credentials."""
    if boto3 is None:
        raise ImportError(
            "boto3 is not installed. Run: pip install boto3\n"
            "boto3 未安装，请运行: pip install boto3"
        )
    try:
        return boto3.client("s3")
    except NoCredentialsError:
        raise RuntimeError(
            "AWS credentials not found. Set AWS_ACCESS_KEY_ID and "
            "AWS_SECRET_ACCESS_KEY environment variables.\n"
            "未找到 AWS 凭据，请设置 AWS_ACCESS_KEY_ID 和 "
            "AWS_SECRET_ACCESS_KEY 环境变量。"
        )


def scan_bucket(bucket: str, prefix: str = "") -> List[dict]:
    """List all objects in an S3 bucket under a given prefix.

    Returns:
        List of dicts with 'key', 'size_bytes', and 'last_modified'.
    """
    s3 = get_s3_client()
    objects = []
    paginator = s3.get_paginator("list_objects_v2")

    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        for obj in page.get("Contents", []):
            objects.append({
                "key": obj["Key"],
                "size_bytes": obj["Size"],
                "last_modified": obj["LastModified"].isoformat(),
            })

    return objects


def check_manifest_against_s3(
    manifest_path: str, bucket: str = None
) -> Tuple[List[str], List[str], List[str]]:
    """Check if s3_path entries in an imaging manifest exist in S3.

    Args:
        manifest_path: Path to the imaging manifest (.xlsx or .csv).
        bucket: Override bucket name. If None, extracted from s3_path.

    Returns:
        Tuple of (found, missing, extra):
        - found: s3_paths that exist in the bucket.
        - missing: s3_paths in manifest but not in bucket.
        - extra: files in bucket but not in manifest (under same prefixes).
    """
    from collector.validator import _read_manifest

    df = _read_manifest(manifest_path)
    if "s3_path" not in df.columns:
        raise ValueError(
            "Manifest does not contain 's3_path' column / "
            "清单中没有 's3_path' 列"
        )

    manifest_paths = set()
    bucket_from_manifest = None
    prefixes = set()

    for val in df["s3_path"].dropna():
        path_str = str(val).strip()
        if path_str.startswith("s3://"):
            parsed = urlparse(path_str)
            bucket_from_manifest = parsed.netloc
            key = parsed.path.lstrip("/")
            manifest_paths.add(key)
            # Collect prefixes (parent directories)
            if "/" in key:
                prefixes.add(key.rsplit("/", 1)[0] + "/")
        else:
            manifest_paths.add(path_str)

    effective_bucket = bucket or bucket_from_manifest
    if not effective_bucket:
        raise ValueError(
            "Cannot determine bucket. Provide --bucket or use s3:// paths / "
            "无法确定桶名，请提供 --bucket 参数或使用 s3:// 路径"
        )

    # Scan the bucket for relevant prefixes
    s3_keys = set()
    for prefix in prefixes:
        objects = scan_bucket(effective_bucket, prefix)
        for obj in objects:
            s3_keys.add(obj["key"])

    found = sorted(manifest_paths & s3_keys)
    missing = sorted(manifest_paths - s3_keys)
    extra = sorted(s3_keys - manifest_paths)

    return found, missing, extra


def format_s3_check_result(
    found: List[str], missing: List[str], extra: List[str]
) -> str:
    """Format S3 check results for display."""
    lines = []
    lines.append(f"📊 S3 Check Results / S3 检查结果:")
    lines.append(f"  ✅ Found / 已找到: {len(found)}")
    lines.append(f"  ❌ Missing / 缺失: {len(missing)}")
    lines.append(f"  ⚠️  Extra / 多余: {len(extra)}")

    if missing:
        lines.append(f"\n❌ Missing files / 缺失的文件:")
        for path in missing:
            lines.append(f"  • {path}")

    if extra:
        lines.append(f"\n⚠️  Extra files (not in manifest) / 多余文件 (不在清单中):")
        for path in extra[:20]:  # limit display
            lines.append(f"  • {path}")
        if len(extra) > 20:
            lines.append(f"  ... and {len(extra) - 20} more")

    return "\n".join(lines)
