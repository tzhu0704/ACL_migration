#!/usr/bin/env python3
"""
测试单个文件的ACL迁移
"""

import subprocess
import sys
import os

def test_acl_migration(source_file, dest_file, domain=None):
    print(f"测试ACL迁移:")
    print(f"源文件: {source_file}")
    print(f"目标文件: {dest_file}")
    print(f"域名: {domain or '无'}")
    print("=" * 60)
    
    # 获取源文件POSIX ACL
    print("1. 获取源文件POSIX ACL:")
    result = subprocess.run(['getfacl', source_file], capture_output=True, text=True)
    if result.returncode == 0:
        print(result.stdout)
    else:
        print(f"错误: {result.stderr}")
        return
    
    # 解析ACL并生成NFSv4 ACL
    print("2. 生成NFSv4 ACL条目:")
    nfs4_acls = []
    
    for line in result.stdout.split('\n'):
        line = line.strip()
        if line.startswith('user:') and ':' in line:
            parts = line.split(':')
            if len(parts) >= 3 and parts[1]:  # 扩展用户ACL
                user = parts[1]
                perms = parts[2]
                
                # 简单权限映射
                nfs4_perms = ""
                if 'r' in perms:
                    nfs4_perms += 'r'
                if 'w' in perms:
                    nfs4_perms += 'w'
                if 'x' in perms:
                    nfs4_perms += 'x'
                
                if nfs4_perms:
                    full_user = f"{user}@{domain}" if domain else user
                    acl_entry = f"A::{full_user}:{nfs4_perms}"
                    nfs4_acls.append(acl_entry)
                    print(f"  {line} -> {acl_entry}")
        
        elif line.startswith('group:') and ':' in line:
            parts = line.split(':')
            if len(parts) >= 3 and parts[1]:  # 扩展组ACL
                group = parts[1]
                perms = parts[2]
                
                # 简单权限映射
                nfs4_perms = ""
                if 'r' in perms:
                    nfs4_perms += 'r'
                if 'w' in perms:
                    nfs4_perms += 'w'
                if 'x' in perms:
                    nfs4_perms += 'x'
                
                if nfs4_perms:
                    full_group = f"{group}@{domain}" if domain else group
                    acl_entry = f"A:g:{full_group}:{nfs4_perms}"
                    nfs4_acls.append(acl_entry)
                    print(f"  {line} -> {acl_entry}")
    
    if not nfs4_acls:
        print("  没有扩展ACL需要迁移")
        return
    
    # 应用NFSv4 ACL
    print(f"\n3. 应用NFSv4 ACL到目标文件:")
    for acl in nfs4_acls:
        print(f"  应用: {acl}")
        result = subprocess.run(['nfs4_setfacl', '-a', acl, dest_file], 
                              capture_output=True, text=True)
        if result.returncode == 0:
            print(f"    ✓ 成功")
        else:
            print(f"    ✗ 失败: {result.stderr.strip()}")
    
    # 显示结果
    print(f"\n4. 迁移后的NFSv4 ACL:")
    result = subprocess.run(['nfs4_getfacl', dest_file], capture_output=True, text=True)
    if result.returncode == 0:
        print(result.stdout)
    else:
        print(f"错误: {result.stderr}")

def main():
    if len(sys.argv) < 3:
        print("用法: python3 test_single_acl.py <源文件> <目标文件> [域名]")
        print("示例: python3 test_single_acl.py /mnt/lustre/backup/origin/export-marker.json /mnt/netapp/vol0/dest/export-marker.json mpdemo1.example.com")
        sys.exit(1)
    
    source_file = sys.argv[1]
    dest_file = sys.argv[2]
    domain = sys.argv[3] if len(sys.argv) > 3 else None
    
    if not os.path.exists(source_file):
        print(f"错误: 源文件不存在: {source_file}")
        sys.exit(1)
    
    if not os.path.exists(dest_file):
        print(f"错误: 目标文件不存在: {dest_file}")
        sys.exit(1)
    
    test_acl_migration(source_file, dest_file, domain)

if __name__ == '__main__':
    main()