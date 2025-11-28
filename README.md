# POSIX ACL 到 NFSv4 ACL 迁移工具

从 Lustre (POSIX ACL) 迁移到 FSx for NetApp ONTAP (NFSv4 ACL) 的完整解决方案。

## 快速开始

```bash
# 1. 克隆项目
git clone <repository>
cd ACL_migration

# 2. 安装依赖
sudo yum install -y nfs4-acl-tools acl python3

# 3. 基本迁移
sudo ./acl_migration.sh -s /mnt/lustre/data -d /mnt/netapp/data --ownership
```

## 核心功能

- ✅ **所有权迁移**: 迁移文件所有者和组
- ✅ **ACL权限迁移**: POSIX ACL → NFSv4 ACL 自动转换
- ✅ **增量迁移**: 断点续传，跳过已迁移文件
- ✅ **文件夹模式**: 只迁移目录ACL，跳过文件
- ✅ **并发处理**: 多线程提升性能
- ✅ **完整日志**: 详细记录和错误追踪
- ✅ **数据库管理**: SQLite 记录迁移状态

## 命令行工具

### 1. 主迁移工具 - `acl_migration.sh`

```bash
# 基本语法
./acl_migration.sh -s <源路径> -d <目标路径> [选项]

# 常用选项
-s, --source PATH       源路径 (POSIX ACL)
-d, --dest PATH         目标路径 (NFSv4 ACL)  
-w, --workers NUM       并发线程数 (默认: 4)
-i, --incremental       增量模式
--ownership             迁移所有权
--folderonly            只迁移文件夹
--domain DOMAIN         NFSv4域名
--debug                 调试模式
-b, --background        后台运行
```

### 2. 数据库管理 - `manage_db.sh`

```bash
# 查看迁移统计
./manage_db.sh stats

# 重置迁移记录
./manage_db.sh reset

# 备份数据库
./manage_db.sh backup

# 恢复数据库
./manage_db.sh restore
```

### 3. 调试工具

```bash
# 诊断所有权问题
python3 debug_ownership.py <源文件> <目标文件>

# 快速修复单文件所有权
./fix_ownership.sh <源文件> <目标文件>
```

## 使用场景

### 场景 1: 单文件迁移

```bash
# 只迁移ACL
./acl_migration.sh \
  -s /mnt/lustre/backup/origin/file.txt \
  -d /mnt/netapp/vol0/dest/file.txt

# 迁移所有权+ACL
sudo ./acl_migration.sh \
  -s /mnt/lustre/backup/origin/file.txt \
  -d /mnt/netapp/vol0/dest/file.txt \
  --ownership --domain example.com
```

### 场景 2: 目录批量迁移

```bash
# 基本目录迁移
./acl_migration.sh \
  -s /mnt/lustre/data \
  -d /mnt/netapp/data \
  -w 8

# 完整迁移 (推荐)
sudo ./acl_migration.sh \
  -s /mnt/lustre/data \
  -d /mnt/netapp/data \
  -w 8 --ownership --incremental --debug
```

### 场景 3: 大数据集迁移

```bash
# 后台运行
sudo ./acl_migration.sh \
  -s /mnt/lustre/bigdata \
  -d /mnt/netapp/bigdata \
  -w 16 --ownership --incremental --background

# 监控进度
tail -f logs/acl_migration_*.log

# 分批处理
for dir in batch1 batch2 batch3; do
  sudo ./acl_migration.sh \
    -s /mnt/lustre/data/$dir \
    -d /mnt/netapp/data/$dir \
    -w 8 --ownership --incremental
done
```

### 场景 4: 增量同步

```bash
# 首次完整迁移
sudo ./acl_migration.sh \
  -s /mnt/lustre/data \
  -d /mnt/netapp/data \
  --ownership --incremental

# 定期增量同步 (cron)
0 2 * * * /opt/acl/ACL_migration/acl_migration.sh \
  -s /mnt/lustre/data \
  -d /mnt/netapp/data \
  --ownership --incremental --background
```

### 场景 5: 只迁移文件夹ACL

适用于只需要设置目录权限的场景，可显著提升性能。

```bash
# 只迁移目录的ACL，跳过所有文件
sudo ./acl_migration.sh \
  -s /mnt/lustre/data \
  -d /mnt/netapp/data \
  --folderonly --ownership

# 结合增量模式
sudo ./acl_migration.sh \
  -s /mnt/lustre/data \
  -d /mnt/netapp/data \
  --folderonly --ownership --incremental

# 分阶段迁移：先目录后文件
# 第一步: 迁移所有目录
sudo ./acl_migration.sh \
  -s /mnt/lustre/data \
  -d /mnt/netapp/data \
  --folderonly --ownership --incremental

# 第二步: 迁移所有文件
sudo ./acl_migration.sh \
  -s /mnt/lustre/data \
  -d /mnt/netapp/data \
  --ownership --incremental
```

**性能对比** (测试环境: 100个目录 + 10,000个文件):

| 模式 | 处理项目数 | 耗时 | 性能提升 |
|------|-----------|------|----------|
| 正常模式 | 10,100 | 45分钟 | - |
| --folderonly | 100 | 2分钟 | 22.5倍 |

### 场景 6: 故障恢复

```bash
# 查看迁移状态
./manage_db.sh stats

# 从中断点继续
sudo ./acl_migration.sh \
  -s /mnt/lustre/data \
  -d /mnt/netapp/data \
  --ownership --incremental

# 重新开始 (清除记录)
./manage_db.sh reset
sudo ./acl_migration.sh \
  -s /mnt/lustre/data \
  -d /mnt/netapp/data \
  --ownership
```

## 完整迁移流程

### 步骤 1: 环境准备

```bash
# 检查依赖
nfs4_setfacl --help
getfacl --help
python3 --version

# 检查挂载
mount | grep -E "(lustre|nfs)"

# 检查权限
ls -la /mnt/lustre/data
ls -la /mnt/netapp/data
```

### 步骤 2: 数据迁移 (可选)

```bash
# 使用 rsync 迁移数据
rsync -avP --numeric-ids \
  /mnt/lustre/data/ \
  /mnt/netapp/data/
```

### 步骤 3: ACL 迁移

```bash
# 测试单个文件
sudo ./acl_migration.sh \
  -s /mnt/lustre/data/test.txt \
  -d /mnt/netapp/data/test.txt \
  --ownership --debug

# 批量迁移
sudo ./acl_migration.sh \
  -s /mnt/lustre/data \
  -d /mnt/netapp/data \
  -w 8 --ownership --incremental --debug
```

### 步骤 4: 验证结果

```bash
# 检查所有权
ls -la /mnt/netapp/data/

# 检查ACL
nfs4_getfacl /mnt/netapp/data/sample_file

# 查看统计
./manage_db.sh stats
```

## 权限映射规则

### POSIX → NFSv4 转换

| POSIX ACL | NFSv4 ACL | 说明 |
|-----------|-----------|------|
| `user:john:rwx` | `A::john:rwx` | 用户权限 |
| `group:dev:rw-` | `A:g:dev:rw` | 组权限 |
| `user:bob:r--` | `A::bob:r` | 只读权限 |

### 域名映射

```bash
# 不指定域名
user:john:rwx → A::john:rwx

# 指定域名
--domain example.com
user:john:rwx → A::john@example.com:rwx
```

## 性能调优

### 并发设置

```bash
# CPU 核心数 × 2
nproc  # 查看核心数
./acl_migration.sh -s /src -d /dest -w 16
```

### 使用 --folderonly 加速

当文件数量远大于目录数量时，使用 `--folderonly` 可以显著提升性能：

```bash
# 假设有 10,000 个文件和 100 个目录
# 使用 --folderonly 可以跳过 10,000 个文件，只处理 100 个目录
sudo ./acl_migration.sh \
  -s /mnt/lustre/project \
  -d /mnt/netapp/project \
  --folderonly --ownership -w 8

# 性能提升: 从 45 分钟减少到 2 分钟
```

### 内存优化

```bash
# 大文件系统分批处理
find /mnt/lustre/data -maxdepth 1 -type d | \
while read dir; do
  ./acl_migration.sh -s "$dir" -d "/mnt/netapp/data/$(basename "$dir")" -w 8
done
```

### 网络优化

```bash
# 本地日志存储
./acl_migration.sh -s /src -d /dest -l /tmp/acl_logs
```

## 参数详细说明

### --folderonly (文件夹模式)

**功能**: 只迁移目录的ACL，跳过所有文件

**适用场景**:
- 只需要设置目录权限
- 文件数量远大于目录数量
- 需要快速完成目录权限设置
- 分阶段迁移策略

**使用示例**:
```bash
# 基本用法
./acl_migration.sh -s /src -d /dest --folderonly

# 结合所有权迁移
sudo ./acl_migration.sh -s /src -d /dest --folderonly --ownership

# 完整参数
sudo ./acl_migration.sh -s /src -d /dest \
  --folderonly --ownership --incremental -w 8 --debug
```

**注意事项**:
- 文件的ACL不会被迁移
- 目标目录结构必须已存在
- 可以与 `--incremental` 组合使用
- 建议使用 `--debug` 查看详细信息

### --ownership (所有权迁移)

**功能**: 迁移文件/目录的所有者和组

**注意**: 需要 sudo 权限，确保用户/组在目标系统中存在

### --incremental (增量模式)

**功能**: 跳过已成功迁移的文件，支持断点续传

**工作原理**: 使用SQLite数据库记录迁移状态和文件修改时间

### --domain (域名映射)

**功能**: 为NFSv4 ACL添加域名后缀

**示例**: `--domain example.com` 将 `user:john:rwx` 转换为 `A::john@example.com:rwx`

## 故障排查

### 常见错误

```bash
# 1. 权限不足
sudo ./acl_migration.sh -s /src -d /dest --ownership

# 2. 用户不存在
id username  # 检查用户
sudo useradd username  # 创建用户

# 3. 组不存在  
getent group groupname  # 检查组
sudo groupadd groupname  # 创建组

# 4. NFSv4 不支持
mount | grep nfs4  # 检查挂载类型

# 5. 调试模式
./acl_migration.sh -s /src -d /dest --debug

# 6. 所有权迁移失败
# 检查用户/组是否存在
id bob
getent group wlogins

# 创建缺失的用户/组
sudo useradd bob
sudo groupadd wlogins

# 使用调试工具诊断
python3 debug_ownership.py /mnt/lustre/file.txt /mnt/netapp/file.txt

# 快速修复单文件
./fix_ownership.sh /mnt/lustre/file.txt /mnt/netapp/file.txt
```

### 日志分析

```bash
# 查看错误
grep ERROR logs/acl_migration_*.log

# 查看成功数量
grep "成功:" logs/acl_migration_*.log | wc -l

# 查看失败文件
grep "失败:" logs/acl_migration_*.log
```

### 性能监控

```bash
# 监控进程
ps aux | grep acl_migration

# 监控资源
top -p $(pgrep -f acl_migration)

# 监控进度
tail -f logs/acl_migration_*.log | grep -E "(成功|失败|跳过)"
```

## 最佳实践

### 1. 迁移前准备

- ✅ 备份重要数据
- ✅ 测试小规模数据集
- ✅ 确认用户/组映射
- ✅ 检查文件系统兼容性

### 2. 迁移执行

- ✅ 使用增量模式
- ✅ 启用调试日志
- ✅ 合理设置并发数
- ✅ 监控系统资源

### 3. 迁移后验证

- ✅ 抽样检查文件权限
- ✅ 验证应用程序访问
- ✅ 检查迁移统计
- ✅ 保留迁移日志

## 项目结构

```
ACL_migration/
├── acl_migration.sh          # 主迁移脚本
├── manage_db.sh              # 数据库管理工具
├── app/
│   ├── acl_migration_tool.py # Python核心工具
│   ├── diagnose_acl.py       # ACL诊断工具
│   └── setup_random_acl.py   # 测试ACL设置
├── logs/                     # 日志和数据库
│   ├── acl_migration_*.log   # 迁移日志
│   └── acl_migration.db      # SQLite数据库
└── README.md                 # 本文件
```

## 技术支持

遇到问题时的调试步骤：

1. **查看日志**: `tail -f logs/acl_migration_*.log`
2. **检查统计**: `./manage_db.sh stats`
3. **单文件测试**: 使用 `debug_ownership.py`
4. **重置重试**: `./manage_db.sh reset`

## 许可证

MIT License - 详见 LICENSE 文件