#!/bin/bash

# Random POSIX ACL Setup Tool Shell Wrapper

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_TOOL="${SCRIPT_DIR}/app/setup_random_acl.py"

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

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

show_help() {
    cat << EOF
Random POSIX ACL Setup Tool

用法: $0 [选项]

选项:
    -d, --directory DIR     目标目录路径 [必需]
    -p, --percentage NUM    处理文件的百分比 (默认: 50)
    -h, --help              显示此帮助信息

示例:
    # 为50%的文件设置随机ACL
    $0 -d /path/to/directory
    
    # 为80%的文件设置随机ACL
    $0 -d /path/to/directory -p 80

预定义用户: tzhu, mary, bob, peter, john, laura, demouser1, demouser2, demouser3
预定义组: wlogins, dev1, dev0_test1, dev0

注意:
    - 需要安装 acl 包 (setfacl 命令)
    - 需要对目标目录有写权限
    - 每个文件会随机分配1-3个用户和1-2个组的ACL

EOF
}

check_dependencies() {
    print_info "检查依赖..."
    
    if [[ ! -f "$PYTHON_TOOL" ]]; then
        print_error "Python 工具不存在: $PYTHON_TOOL"
        exit 1
    fi
    
    # 检查 Python
    PYTHON_CMD=""
    if command -v python3 &> /dev/null; then
        PYTHON_CMD="python3"
    elif command -v python &> /dev/null; then
        if python -c "import sys; exit(0 if sys.version_info[0] >= 3 else 1)" 2>/dev/null; then
            PYTHON_CMD="python"
        fi
    fi
    
    if [[ -z "$PYTHON_CMD" ]]; then
        print_error "Python 3 未安装或不可用"
        exit 1
    fi
    
    # 检查 setfacl
    if ! command -v setfacl &> /dev/null; then
        print_error "setfacl 未找到，请安装 acl 包:"
        print_error "  RHEL/CentOS: sudo yum install -y acl"
        print_error "  Ubuntu/Debian: sudo apt-get install -y acl"
        exit 1
    fi
    
    print_success "依赖检查通过"
}

main() {
    DIRECTORY=""
    PERCENTAGE=50
    
    while [[ $# -gt 0 ]]; do
        case $1 in
            -d|--directory)
                DIRECTORY="$2"
                shift 2
                ;;
            -p|--percentage)
                PERCENTAGE="$2"
                shift 2
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
    
    if [[ -z "$DIRECTORY" ]]; then
        print_error "必须指定目标目录"
        show_help
        exit 1
    fi
    
    check_dependencies
    
    print_info "开始设置随机ACL..."
    print_info "目标目录: $DIRECTORY"
    print_info "处理百分比: $PERCENTAGE%"
    echo
    
    if "$PYTHON_CMD" "$PYTHON_TOOL" -d "$DIRECTORY" -p "$PERCENTAGE"; then
        print_success "随机ACL设置完成"
    else
        print_error "随机ACL设置失败"
        exit 1
    fi
}

main "$@"