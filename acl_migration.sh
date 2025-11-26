#!/bin/bash

# ACL Migration Tool Shell Wrapper
# 用于调用 POSIX ACL 到 NFSv4 ACL 迁移工具

set -euo pipefail

# 脚本目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_TOOL="${SCRIPT_DIR}/app/acl_migration_tool.py"
LOGS_DIR="${SCRIPT_DIR}/logs"

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 打印带颜色的消息
print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 显示帮助信息
show_help() {
    cat << EOF
================================================================================
ACL Migration Tool - POSIX ACL 到 NFSv4 ACL 迁移工具
================================================================================

用法: $0 [选项]

必需参数:
    -s, --source PATH       源路径 (文件或目录, POSIX ACL)
    -d, --dest PATH         目标路径 (文件或目录, NFSv4 ACL)

可选参数:
    -w, --workers NUM       并发线程数 (默认: 4, 范围: 1-32)
    -i, --incremental       启用增量模式 (跳过已迁移的文件)
    --ownership             迁移文件所有权 (默认只迁移ACL)
    -b, --background        后台运行模式 (不显示实时输出)
    --debug                 启用调试模式 (详细日志输出)
    --domain DOMAIN         NFSv4域名后缀 (例: mpdemo1.example.com)
    --reset-db              重置数据库，清除所有迁移记录
    --show-db-stats         显示数据库统计信息
    -h, --help              显示此帮助信息

================================================================================
使用场景和示例
================================================================================

1. 基本迁移 (只迁移ACL权限):
    # 目录迁移
    $0 -s /mnt/lustre/data -d /mnt/netapp/data
    
    # 单文件迁移
    $0 -s /mnt/lustre/data/file.txt -d /mnt/netapp/data/file.txt

2. 完整迁移 (迁移所有权和ACL):
    # 目录完整迁移
    $0 -s /mnt/lustre/data -d /mnt/netapp/data --ownership
    
    # 单文件完整迁移，指定域名
    $0 -s /mnt/lustre/backup/origin/export-marker.json \\
       -d /mnt/netapp/vol0/dest/export-marker.json \\
       --ownership --domain mpdemo1.example.com

3. 高性能迁移:
    # 增量迁移，16个并发线程
    $0 -s /mnt/lustre/data -d /mnt/netapp/data -w 16 -i
    
    # 后台运行，适合大数据量迁移
    $0 -s /mnt/lustre/data -d /mnt/netapp/data -w 8 -b

4. 调试和监控:
    # 启用调试模式
    $0 -s /mnt/lustre/data -d /mnt/netapp/data --debug
    
    # 查看数据库统计
    $0 --show-db-stats
    
    # 重置迁移记录
    $0 --reset-db

5. 交互式模式:
    # 无参数运行，进入交互式配置
    $0

6. 分批迁移 (大数据集推荐):
    # 按子目录分批迁移
    $0 -s /mnt/lustre/data/batch1 -d /mnt/netapp/data/batch1 -w 8 -i
    $0 -s /mnt/lustre/data/batch2 -d /mnt/netapp/data/batch2 -w 8 -i
    $0 -s /mnt/lustre/data/batch3 -d /mnt/netapp/data/batch3 -w 8 -i

7. 组合使用 (生产环境推荐):
    # 完整迁移 + 增量模式 + 后台运行 + 调试
    $0 -s /mnt/lustre/data -d /mnt/netapp/data \\
       --ownership -i -b --debug -w 12

================================================================================
参数详细说明
================================================================================

源路径 (-s, --source):
    - 支持文件或目录
    - 必须存在且可读
    - 应该具有 POSIX ACL
    - 示例: /mnt/lustre/data, /path/to/file.txt

目标路径 (-d, --dest):
    - 必须与源路径类型匹配 (文件对文件，目录对目录)
    - 必须存在且可写
    - 必须支持 NFSv4 ACL
    - 示例: /mnt/netapp/data, /path/to/target.txt

并发线程数 (-w, --workers):
    - 范围: 1-32
    - 推荐值: CPU核心数 × 2
    - 默认: 4
    - 注意: 过高可能导致系统负载过重

增量模式 (-i, --incremental):
    - 跳过已成功迁移的文件
    - 基于文件修改时间和ACL哈希值判断
    - 适合断点续传和定期同步
    - 使用 SQLite 数据库记录状态

所有权迁移 (--ownership):
    - 同时迁移文件所有者和组所有者
    - 需要相应的系统权限
    - 默认只迁移 ACL 权限

后台运行 (-b, --background):
    - 以 nohup 方式在后台运行
    - 不显示实时输出
    - 适合大数据量长时间迁移
    - 返回进程ID用于监控

调试模式 (--debug):
    - 输出详细的调试信息
    - 包含每个文件的处理过程
    - 用于故障排查

NFSv4域名 (--domain):
    - 指定 NFSv4 域名后缀
    - 用于用户名映射
    - 示例: mpdemo1.example.com
    - 可选参数，通常由系统自动检测

数据库重置 (--reset-db):
    - 清除所有迁移记录
    - 下次运行将重新迁移所有文件
    - 谨慎使用

数据库统计 (--show-db-stats):
    - 显示迁移统计信息
    - 包含成功、失败、跳过的文件数量
    - 用于监控迁移进度

================================================================================
系统要求和依赖
================================================================================

必需软件:
    - Python 3.6+
    - nfs4-acl-tools (nfs4_setfacl, nfs4_getfacl)
    - acl (getfacl, setfacl)

安装命令:
    # RHEL/CentOS/Amazon Linux
    sudo yum install -y nfs4-acl-tools acl python3
    
    # Ubuntu/Debian
    sudo apt-get install -y nfs4-acl-tools acl python3

文件系统要求:
    - 源: 支持 POSIX ACL (ext4, xfs 等)
    - 目标: 支持 NFSv4 ACL (NFSv4.1 挂载)
    - FSx for NetApp ONTAP: 安全风格必须为 'unified'

权限要求:
    - 读取源文件和ACL的权限
    - 写入目标文件ACL的权限
    - 迁移所有权时需要 chown 权限

================================================================================
输出和日志
================================================================================

日志位置:
    - 目录: ${LOGS_DIR}
    - 文件: acl_migration_YYYYMMDD_HHMMSS.log
    - 数据库: acl_migration.db

日志内容:
    - 迁移进度和统计
    - 成功/失败的文件列表
    - 错误信息和异常堆栈
    - 性能统计信息

实时监控:
    # 查看实时日志
    tail -f ${LOGS_DIR}/acl_migration_*.log
    
    # 查看后台进程
    ps aux | grep acl_migration
    
    # 停止后台进程
    kill <PID>

================================================================================
故障排查
================================================================================

常见问题:

1. "nfs4_setfacl 命令不存在"
   解决: sudo yum install -y nfs4-acl-tools

2. "权限不足"
   解决: 使用 sudo 运行或检查文件权限

3. "目标文件系统不支持 NFSv4 ACL"
   解决: 确认使用 NFSv4.1 挂载，检查安全风格

4. "迁移中断"
   解决: 使用 --incremental 参数继续迁移

5. "性能问题"
   解决: 调整 --workers 参数，使用分批迁移

调试步骤:
    1. 使用 --debug 参数获取详细日志
    2. 检查 ${LOGS_DIR} 中的日志文件
    3. 验证源和目标路径的权限
    4. 测试单个文件迁移
    5. 检查系统资源使用情况

================================================================================
最佳实践
================================================================================

1. 数据迁移流程:
   # 第一步: 迁移数据 (使用 rsync)
   rsync -rlptgoD --progress /mnt/lustre/data/ /mnt/netapp/data/
   
   # 第二步: 迁移 ACL
   $0 -s /mnt/lustre/data -d /mnt/netapp/data -w 8 -i
   
   # 第三步: 迁移所有权 (如需要)
   $0 -s /mnt/lustre/data -d /mnt/netapp/data --ownership -i

2. 大数据集迁移:
   - 使用增量模式 (-i)
   - 适当调整并发数 (-w)
   - 分批处理子目录
   - 后台运行 (-b)

3. 生产环境:
   - 先在测试环境验证
   - 使用调试模式排查问题
   - 定期检查数据库统计
   - 保留迁移日志

4. 性能优化:
   - 并发数 = CPU核心数 × 2
   - 避免网络存储的高延迟
   - 监控系统资源使用
   - 使用本地SSD作为日志存储

================================================================================
版本信息
================================================================================

工具版本: 2.0
支持的ACL类型: POSIX ACL → NFSv4 ACL
支持的文件系统: ext4, xfs → NFSv4.1
兼容性: Linux (RHEL/CentOS/Ubuntu/Amazon Linux)

更多信息请参考: ${SCRIPT_DIR}/docs/README_ACL_MIGRATION.md

EOF
}

# 检查依赖
check_dependencies() {
    print_info "检查依赖..."
    
    # 检查 Python 工具
    if [[ ! -f "$PYTHON_TOOL" ]]; then
        print_error "Python 工具不存在: $PYTHON_TOOL"
        exit 1
    fi
    
    # 检查 Python (优先 python3)
    PYTHON_CMD=""
    if command -v python3 &> /dev/null; then
        PYTHON_CMD="python3"
    elif command -v python &> /dev/null; then
        # 检查 python 版本是否为 3.x
        if python -c "import sys; exit(0 if sys.version_info[0] >= 3 else 1)" 2>/dev/null; then
            PYTHON_CMD="python"
        fi
    fi
    
    if [[ -z "$PYTHON_CMD" ]]; then
        print_error "Python 3 未安装或不可用"
        exit 1
    fi
    
    print_info "使用 Python 命令: $PYTHON_CMD"
    
    # 检查 nfs4-acl-tools
    if ! command -v nfs4_setfacl &> /dev/null; then
        print_warning "nfs4_setfacl 未找到，请安装 nfs4-acl-tools:"
        print_warning "  RHEL/CentOS: sudo yum install -y nfs4-acl-tools"
        print_warning "  Ubuntu/Debian: sudo apt-get install -y nfs4-acl-tools"
        exit 1
    fi
    
    # 检查 getfacl
    if ! command -v getfacl &> /dev/null; then
        print_error "getfacl 未找到，请安装 acl 包"
        exit 1
    fi
    
    print_success "依赖检查通过"
}

# 验证目录
validate_directory() {
    local dir="$1"
    local name="$2"
    
    if [[ ! -d "$dir" ]]; then
        print_error "$name 不存在: $dir"
        return 1
    fi
    
    if [[ ! -r "$dir" ]]; then
        print_error "$name 不可读: $dir"
        return 1
    fi
    
    return 0
}

# 交互式获取参数
interactive_mode() {
    print_info "进入交互式配置模式"
    echo
    
    # 获取源路径
    while true; do
        read -p "请输入源路径 (文件或目录, POSIX ACL): " SOURCE_DIR
        if [[ -n "$SOURCE_DIR" ]] && [[ -e "$SOURCE_DIR" ]]; then
            break
        else
            print_error "源路径不存在: $SOURCE_DIR"
        fi
    done
    
    # 获取目标路径
    while true; do
        read -p "请输入目标路径 (文件或目录, NFSv4 ACL): " DEST_DIR
        if [[ -n "$DEST_DIR" ]]; then
            if [[ -f "$SOURCE_DIR" ]]; then
                # 单文件模式：目标必须是文件
                if [[ -f "$DEST_DIR" ]]; then
                    break
                else
                    print_error "单文件模式下，目标必须是文件: $DEST_DIR"
                fi
            else
                # 目录模式：目标必须是目录
                if [[ -d "$DEST_DIR" ]]; then
                    break
                else
                    print_error "目录模式下，目标必须是目录: $DEST_DIR"
                fi
            fi
        fi
    done
    
    # 获取并发数
    read -p "并发线程数 [4]: " WORKERS
    WORKERS=${WORKERS:-4}
    
    # 验证并发数
    if ! [[ "$WORKERS" =~ ^[0-9]+$ ]] || [[ "$WORKERS" -lt 1 ]]; then
        print_warning "无效的并发数，使用默认值: 4"
        WORKERS=4
    fi
    
    # 增量模式
    read -p "启用增量模式? (y/N): " INCREMENTAL_INPUT
    if [[ "$INCREMENTAL_INPUT" =~ ^[Yy]$ ]]; then
        INCREMENTAL=true
    else
        INCREMENTAL=false
    fi
    
    # 所有权迁移
    read -p "迁移文件所有权? (y/N): " OWNERSHIP_INPUT
    if [[ "$OWNERSHIP_INPUT" =~ ^[Yy]$ ]]; then
        OWNERSHIP=true
    else
        OWNERSHIP=false
    fi
    
    # 后台运行
    read -p "后台运行? (y/N): " BACKGROUND_INPUT
    if [[ "$BACKGROUND_INPUT" =~ ^[Yy]$ ]]; then
        BACKGROUND=true
    else
        BACKGROUND=false
    fi
    
    # 调试模式
    read -p "启用调试模式? (y/N): " DEBUG_INPUT
    if [[ "$DEBUG_INPUT" =~ ^[Yy]$ ]]; then
        DEBUG=true
    else
        DEBUG=false
    fi
    
    echo
    print_info "配置摘要:"
    echo "  源路径: $SOURCE_DIR"
    echo "  目标路径: $DEST_DIR"
    echo "  并发数: $WORKERS"
    echo "  增量模式: $INCREMENTAL"
    echo "  迁移所有权: $([ "$OWNERSHIP" = true ] && echo "是" || echo "否")"
    echo "  后台运行: $([ "$BACKGROUND" = true ] && echo "是" || echo "否")"
    echo "  调试模式: $([ "$DEBUG" = true ] && echo "是" || echo "否")"
    echo "  日志目录: $LOGS_DIR"
    echo
    
    read -p "确认开始迁移? (y/N): " CONFIRM
    if [[ ! "$CONFIRM" =~ ^[Yy]$ ]]; then
        print_info "迁移已取消"
        exit 0
    fi
}

# 创建日志目录
setup_logging() {
    if [[ ! -d "$LOGS_DIR" ]]; then
        mkdir -p "$LOGS_DIR"
        print_info "创建日志目录: $LOGS_DIR"
    fi
}

# 运行迁移
run_migration() {
    local args=()
    
    args+=("-s" "$SOURCE_DIR")
    args+=("-d" "$DEST_DIR")
    args+=("-l" "$LOGS_DIR")
    args+=("-w" "$WORKERS")
    
    if [[ "$INCREMENTAL" == true ]]; then
        args+=("--incremental")
    fi
    
    if [[ "$OWNERSHIP" == true ]]; then
        args+=("--ownership")
    fi
    
    if [[ "$BACKGROUND" == true ]]; then
        args+=("--background")
    fi
    
    if [[ "$DEBUG" == true ]]; then
        args+=("--debug")
    fi
    
    if [[ -n "$DOMAIN" ]]; then
        args+=("--domain" "$DOMAIN")
    fi
    
    if [[ "$RESET_DB" == true ]]; then
        args+=("--reset-db")
    fi
    
    if [[ "$SHOW_DB_STATS" == true ]]; then
        args+=("--show-db-stats")
    fi
    
    print_info "开始执行迁移..."
    print_info "命令: $PYTHON_CMD $PYTHON_TOOL ${args[*]}"
    echo
    
    # 执行迁移
    if [[ "$BACKGROUND" == true ]]; then
        print_info "后台运行中..."
        nohup "$PYTHON_CMD" "$PYTHON_TOOL" "${args[@]}" > /dev/null 2>&1 &
        BG_PID=$!
        print_success "迁移已在后台启动，进程 ID: $BG_PID"
        print_info "查看日志: tail -f $LOGS_DIR/*.log"
        print_info "停止迁移: kill $BG_PID"
    elif "$PYTHON_CMD" "$PYTHON_TOOL" "${args[@]}"; then
        print_success "迁移完成"
        echo
        print_info "查看日志文件:"
        ls -la "$LOGS_DIR"/*.log 2>/dev/null || true
    else
        print_error "迁移失败"
        exit 1
    fi
}

# 主函数
main() {
    # 默认值
    SOURCE_DIR=""
    DEST_DIR=""
    WORKERS=4
    INCREMENTAL=false
    OWNERSHIP=false
    BACKGROUND=false
    DEBUG=false
    DOMAIN=""
    RESET_DB=false
    SHOW_DB_STATS=false
    
    # 解析命令行参数
    while [[ $# -gt 0 ]]; do
        case $1 in
            -s|--source)
                SOURCE_DIR="$2"
                shift 2
                ;;
            -d|--dest)
                DEST_DIR="$2"
                shift 2
                ;;
            -w|--workers)
                WORKERS="$2"
                shift 2
                ;;
            -i|--incremental)
                INCREMENTAL=true
                shift
                ;;
            --ownership)
                OWNERSHIP=true
                shift
                ;;
            -b|--background)
                BACKGROUND=true
                shift
                ;;
            --debug)
                DEBUG=true
                shift
                ;;
            --domain)
                DOMAIN="$2"
                shift 2
                ;;
            --reset-db)
                RESET_DB=true
                shift
                ;;
            --show-db-stats)
                SHOW_DB_STATS=true
                shift
                ;;
            -h|--help)
                show_help
                exit 0
                ;;
            *)
                print_error "未知参数: $1"
                show_help
                exit 1
                ;;
        esac
    done
    
    # 数据库操作不需要检查nfs4工具，但需要检查Python
    if [[ "$RESET_DB" == true || "$SHOW_DB_STATS" == true ]]; then
        # 只检查Python
        if command -v python3 &> /dev/null; then
            PYTHON_CMD="python3"
        elif command -v python &> /dev/null; then
            if python -c "import sys; exit(0 if sys.version_info[0] >= 3 else 1)" 2>/dev/null; then
                PYTHON_CMD="python"
            fi
        fi
        
        if [[ -z "${PYTHON_CMD:-}" ]]; then
            print_error "Python 3 未安装或不可用"
            exit 1
        fi
    else
        check_dependencies
    fi
    
    # 设置日志
    setup_logging
    
    # 数据库操作不需要源和目标路径
    if [[ "$RESET_DB" == true || "$SHOW_DB_STATS" == true ]]; then
        # 数据库操作模式
        SOURCE_DIR="/tmp"  # 占位符
        DEST_DIR="/tmp"   # 占位符
    elif [[ -z "$SOURCE_DIR" || -z "$DEST_DIR" ]]; then
        # 如果没有提供必需参数，进入交互模式
        interactive_mode
    else
        # 只在非数据库操作模式下验证参数
        if [[ "$RESET_DB" != true && "$SHOW_DB_STATS" != true ]]; then
            # 验证参数
            if [[ ! -e "$SOURCE_DIR" ]]; then
                print_error "源路径不存在: $SOURCE_DIR"
                exit 1
            fi
            
            if [[ -f "$SOURCE_DIR" ]]; then
                # 单文件模式
                if [[ ! -f "$DEST_DIR" ]]; then
                    print_error "单文件模式下，目标必须是文件: $DEST_DIR"
                    exit 1
                fi
            else
                # 目录模式
                if [[ ! -d "$DEST_DIR" ]]; then
                    print_error "目录模式下，目标必须是目录: $DEST_DIR"
                    exit 1
                fi
            fi
        fi
        
        # 验证并发数
        if ! [[ "$WORKERS" =~ ^[0-9]+$ ]] || [[ "$WORKERS" -lt 1 ]]; then
            print_error "无效的并发数: $WORKERS"
            exit 1
        fi
    fi
    
    # 运行迁移
    run_migration
}

# 信号处理
trap 'print_warning "迁移被中断"; exit 130' INT TERM

# 执行主函数
main "$@"