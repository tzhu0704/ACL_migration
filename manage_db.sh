#!/bin/bash

# ACL迁移数据库管理工具

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_TOOL="${SCRIPT_DIR}/app/acl_migration_tool.py"
DEFAULT_DB="${SCRIPT_DIR}/logs/acl_migration.db"

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
ACL迁移数据库管理工具

用法: $0 [选项] [操作]

操作:
    stats       显示数据库统计信息
    reset       重置数据库，清除所有迁移记录
    backup      备份数据库
    restore     恢复数据库

选项:
    --db PATH   指定数据库路径 (默认: ${DEFAULT_DB})
    -h, --help  显示此帮助信息

示例:
    $0 stats                    # 显示统计信息
    $0 reset                    # 重置数据库
    $0 backup                   # 备份数据库
    $0 --db /path/to/db stats   # 指定数据库路径

EOF
}

check_python_tool() {
    if [[ ! -f "$PYTHON_TOOL" ]]; then
        print_error "Python工具不存在: $PYTHON_TOOL"
        exit 1
    fi
}

show_stats() {
    local db_path="$1"
    print_info "显示数据库统计信息: $db_path"
    
    if [[ ! -f "$db_path" ]]; then
        print_warning "数据库文件不存在: $db_path"
        return
    fi
    
    python3 "$PYTHON_TOOL" --show-db-stats --db "$db_path"
}

reset_database() {
    local db_path="$1"
    print_warning "即将重置数据库: $db_path"
    print_warning "这将删除所有迁移记录，操作不可逆！"
    
    read -p "确认重置数据库? (y/N): " confirm
    if [[ ! "$confirm" =~ ^[Yy]$ ]]; then
        print_info "操作已取消"
        return
    fi
    
    python3 "$PYTHON_TOOL" --reset-db --db "$db_path"
    print_success "数据库重置完成"
}

backup_database() {
    local db_path="$1"
    
    if [[ ! -f "$db_path" ]]; then
        print_error "数据库文件不存在: $db_path"
        return 1
    fi
    
    local timestamp=$(date +"%Y%m%d_%H%M%S")
    local backup_path="${db_path}.backup_${timestamp}"
    
    cp "$db_path" "$backup_path"
    print_success "数据库已备份到: $backup_path"
}

restore_database() {
    local db_path="$1"
    
    print_info "可用的备份文件:"
    local backup_files=($(ls "${db_path}.backup_"* 2>/dev/null || true))
    
    if [[ ${#backup_files[@]} -eq 0 ]]; then
        print_warning "没有找到备份文件"
        return 1
    fi
    
    for i in "${!backup_files[@]}"; do
        echo "  $((i+1)). ${backup_files[i]}"
    done
    
    read -p "请选择要恢复的备份文件编号: " choice
    
    if [[ ! "$choice" =~ ^[0-9]+$ ]] || [[ "$choice" -lt 1 ]] || [[ "$choice" -gt ${#backup_files[@]} ]]; then
        print_error "无效的选择"
        return 1
    fi
    
    local selected_backup="${backup_files[$((choice-1))]}"
    
    print_warning "即将从备份恢复数据库"
    print_warning "当前数据库: $db_path"
    print_warning "备份文件: $selected_backup"
    
    read -p "确认恢复? (y/N): " confirm
    if [[ ! "$confirm" =~ ^[Yy]$ ]]; then
        print_info "操作已取消"
        return
    fi
    
    cp "$selected_backup" "$db_path"
    print_success "数据库恢复完成"
}

main() {
    local db_path="$DEFAULT_DB"
    local operation=""
    
    while [[ $# -gt 0 ]]; do
        case $1 in
            --db)
                db_path="$2"
                shift 2
                ;;
            stats|reset|backup|restore)
                operation="$1"
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
    
    if [[ -z "$operation" ]]; then
        print_error "请指定操作"
        show_help
        exit 1
    fi
    
    check_python_tool
    
    case "$operation" in
        stats)
            show_stats "$db_path"
            ;;
        reset)
            reset_database "$db_path"
            ;;
        backup)
            backup_database "$db_path"
            ;;
        restore)
            restore_database "$db_path"
            ;;
    esac
}

main "$@"