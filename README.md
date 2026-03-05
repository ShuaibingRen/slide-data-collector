# slide-data-collector

> 临床切片成像数据的轻量级元数据收集工具

## 场景

```
临床团队提供供体信息 → 制备样本 → 交付给 CRO → CRO 成像 → 通过 S3 交付图像
       ↓                  ↓                         ↓
  填写 donor 元数据  填写 sample 元数据        填写 imaging 元数据
```

三方协作产生的元数据需要统一收集、验证和关联，本工具提供从模板生成到交付校验的完整流程。

## 安装

```bash
git clone https://github.com/ShuaibingRen/slide-data-collector.git
cd slide-data-collector
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

## 命令总览

```
collector
├── template gen    生成 Excel 元数据模板
├── validate        验证已填写的清单
├── s3
│   ├── scan        扫描 S3 桶中的文件
│   └── check       比对清单与 S3 实际内容
└── report          合并三份清单生成交付报告
```

## 使用流程

### 1. 生成 Excel 模板

```bash
# 一次性生成全部模板
collector template gen --type all --output ./output/

# 或逐个生成
collector template gen --type donor --output ./output/
collector template gen --type sample --output ./output/
collector template gen --type imaging --output ./output/
```

输出示例：

```
✅ Generated 3 template(s) / 已生成 3 个模板:
  📄 output/donor_manifest.xlsx
  📄 output/imaging_manifest.xlsx
  📄 output/sample_manifest.xlsx
```

生成的 Excel 包含两个工作表：
- **Instructions - 填写说明**：字段说明、类型、示例值
- **Data - 数据**：实际填写区域，带下拉菜单和数据验证

颜色约定：🔵 蓝色 = 必填，🟡 黄色 = 选填

### 2. 分发模板

| 模板 | 发送给 |
|------|--------|
| `donor_manifest.xlsx` | 临床团队 |
| `sample_manifest.xlsx` | 样本制备方 |
| `imaging_manifest.xlsx` | CRO |

### 3. 验证回收的清单

```bash
# 自动从文件名识别类型
collector validate ./filled/donor_manifest.xlsx

# 手动指定类型
collector validate ./filled/some_file.xlsx --type imaging
```

输出示例（验证通过）：

```
✅ Validation passed! / 验证通过！
```

输出示例（验证失败）：

```
❌ Found 2 error(s) / 发现 2 个错误:
  • Row 3, [gender]: Required field is empty / 必填字段为空
  • Row 4, [data_level]: Invalid value 'XXX'. Allowed: level1, level2 / 无效值
```

### 4. 检查 S3 交付

需要先配置 AWS 凭据：

```bash
export AWS_ACCESS_KEY_ID=your_key
export AWS_SECRET_ACCESS_KEY=your_secret
export AWS_DEFAULT_REGION=us-east-1
```

```bash
# 扫描 S3 桶中的文件
collector s3 scan --bucket my-imaging-bucket --prefix deliveries/
```

输出示例：

```
📦 Found 42 file(s) in s3://my-imaging-bucket/deliveries/
  deliveries/IMG-001.ome.tiff  (2.5 GB)
  deliveries/IMG-002.ome.tiff  (1.8 GB)
  ...
```

```bash
# 比对 imaging 清单中的 s3_path 与 S3 实际内容
collector s3 check ./filled/imaging_manifest.xlsx --bucket my-imaging-bucket
```

输出示例：

```
📊 S3 Check Results / S3 检查结果:
  ✅ Found / 已找到: 40
  ❌ Missing / 缺失: 2
  ⚠️  Extra / 多余: 3

❌ Missing files / 缺失的文件:
  • deliveries/IMG-041.ome.tiff
  • deliveries/IMG-042.ome.tiff
```

### 5. 生成交付报告

```bash
collector report \
  --donor ./filled/donor_manifest.xlsx \
  --sample ./filled/sample_manifest.xlsx \
  --imaging ./filled/imaging_manifest.xlsx \
  --output ./output/delivery_report.xlsx
```

输出示例：

```
📋 Delivery Report Summary / 交付报告概览:
  Total images / 总图像数: 42
  Total samples / 总样本数: 20
  Total donors / 总供体数: 10
  Linked images / 已关联图像: 40
  Unlinked images / 未关联图像: 2

  📁 Report saved to: ./output/delivery_report.xlsx
```

生成的报告包含以下工作表：

| 工作表 | 内容 |
|--------|------|
| Summary - 概览 | 统计摘要 |
| Merged Data - 合并数据 | 三表关联后的完整数据，异常行高亮 |
| Donors - 供体 | 原始供体数据 |
| Samples - 样本 | 原始样本数据 |
| Images - 图像 | 原始成像数据 |

## 数据模型

三层链式结构，通过 ID 关联：

```
Donor (供体)                    Sample (样本)                  Imaging (成像)
├── participant_id ──────────── parent_id
├── gender*                     ├── biospecimen_id ──────────── parent_biospecimen_id
├── age_at_diagnosis            ├── tissue_harvest_site         ├── data_file_id
├── primary_diagnosis           ├── tissue_tumor_status*        ├── filename
├── morphology                  ├── acquisition_method_type*    ├── file_format
├── site_of_resection_or_biopsy ├── preservation_method*        ├── data_level*
├── tissue_or_organ_of_origin                                   ├── s3_path
├── tumor_grade*                                                ├── image_assay_type*
├── clinical_stage_AJCC                                         ├── channel_metadata_filename
├── pathologic_stage_AJCC                                       ├── microscope
├── molecular_subtype                                           ├── software
├── date_of_diagnosis                                           ├── objective
├── date_of_progression                                         ├── nominal_magnification
├── date_of_last_followup                                       ├── lensNA
├── date_of_death                                               ├── PhysicalSizeX/Y
├── vital_status*                                               ├── PhysicalSizeXUnit/YUnit
├── last_known_disease_status                                   ├── Type
├── treatment_type                                              └── Overlap
└── therapeutic_agents

* = 枚举类型（有预定义可选值）
```

可通过修改 `schemas/*.yaml` 自定义字段。

## 配置

编辑 `config.yaml` 设置默认值：

```yaml
s3:
  default_bucket: "my-imaging-bucket"
  region: "us-east-1"
  image_prefix: "deliveries/"

schemas:
  directory: "./schemas"

output:
  directory: "./output"
```

也可通过环境变量 `COLLECTOR_CONFIG` 指定配置文件路径。

## 开发

```bash
git clone https://github.com/ShuaibingRen/slide-data-collector.git
cd slide-data-collector
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
python -m pytest tests/ -v
```
