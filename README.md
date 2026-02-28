# slide-data-collector

> 临床切片成像数据的轻量级（元）数据收集工具

A lightweight CLI tool for collecting metadata across clinical slide imaging workflows.

## 场景 / Scenario

```
外部临床制备样本切片 → 交付给 CRO → CRO 对切片成像 → 通过 S3 交付图像
                        ↓                    ↓
                 填写样本+切片元数据     填写成像元数据
```

## 安装 / Installation

```bash
cd slide-data-collector
pip install -e .
```

## 快速开始 / Quick Start

### 1. 生成 Excel 模板

```bash
# 一次性生成全部模板
collector template gen --type all --output ./output/

# 或逐个生成
collector template gen --type sample --output ./output/
collector template gen --type slide --output ./output/
collector template gen --type imaging --output ./output/
```

生成的 Excel 文件特性：
- 🔵 蓝色字段 = 必填
- 🟡 黄色字段 = 选填
- 下拉菜单自动约束可选值
- 中英双语说明 (Instructions 工作表)

### 2. 分发模板给合作方

| 模板 | 发送给 |
|------|--------|
| `sample_manifest.xlsx` | 临床团队 |
| `slide_manifest.xlsx` | 切片制备方 |
| `imaging_manifest.xlsx` | CRO |

### 3. 验证回收的清单

```bash
# 自动从文件名识别类型
collector validate ./filled/sample_manifest.xlsx

# 手动指定类型
collector validate ./filled/some_file.xlsx --type imaging
```

### 4. 检查 S3 交付

```bash
# 扫描 S3 桶
collector s3 scan --bucket my-imaging-bucket --prefix deliveries/

# 检查 imaging manifest 中的路径是否都存在于 S3
collector s3 check ./filled/imaging_manifest.xlsx --bucket my-imaging-bucket
```

### 5. 生成交付报告

```bash
collector report \
  --sample ./filled/sample_manifest.xlsx \
  --slide ./filled/slide_manifest.xlsx \
  --imaging ./filled/imaging_manifest.xlsx \
  --output ./output/delivery_report.xlsx
```

## 配置 / Configuration

编辑 `config.yaml`:

```yaml
s3:
  default_bucket: "my-imaging-bucket"
  region: "us-east-1"
  image_prefix: "deliveries/"
```

S3 凭据通过环境变量配置:

```bash
export AWS_ACCESS_KEY_ID=your_key
export AWS_SECRET_ACCESS_KEY=your_secret
export AWS_DEFAULT_REGION=us-east-1
```

## 数据模型 / Data Model

```
Sample (样本)          Slide (切片)          Imaging (成像)
├── sample_id ──────── sample_id
├── patient_id         ├── slide_id ──────── slide_id
├── tissue_type        ├── stain_type        ├── image_id
├── diagnosis          ├── section_thickness  ├── s3_path
├── collection_date    ├── antibody_panel     ├── imaging_modality
├── fixation_method    ├── preparation_date   ├── scanner_model
├── clinical_stage     ├── operator           ├── resolution
└── notes              └── notes              ├── file_format
                                              ├── file_size_gb
                                              ├── imaging_date
                                              ├── qc_status
                                              └── qc_notes
```

可通过修改 `schemas/*.yaml` 文件自定义字段。

## 开发 / Development

```bash
pip install -e ".[dev]"
pytest tests/ -v
```
