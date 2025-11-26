#!/usr/bin/env python3
"""
ACL诊断工具 - 用于调试ACL转换问题
"""

import os
import sys
import subprocess
import re
import pwd
import grp
from pathlib import Path

def get_posix_acl(file_path: str):
    """获取POSIX ACL"""
    try:
        result = subprocess.run(
            ['getfacl', '--absolute-names', '--omit-header', file_path],
            capture_output=True,
            text=True,
            check=True
        )
        
        print(f"POSIX ACL for {file_path}:")
        print(result.stdout)
        
        # 解析ACL
        acl_entries = {'user': [], 'group': []}
        
        for line in result.stdout.strip().split('\n'):
            line = line.strip()
            if not line or line.startswith('#'):
                continue
                
            match = re.match(r'(user|group):([^:]*):([rwx-]+)', line)
            if match:
                acl_type, name, perms = match.groups()
                if acl_type == 'user' and name:
                    acl_entries['user'].append({'name': name, 'perms': perms})
                elif acl_type == 'group' and name:
                    acl_entries['group'].append({'name': name, 'perms': perms})
        
        return acl_entries
        
    except subprocess.CalledProcessError as e:
        print(f"获取POSIX ACL失败: {e.stderr}")
        return None

def convert_to_nfs4(acl_entries, file_path: str):
    """转换为NFSv4 ACL"""
    nfs4_acls = []
    is_dir = os.path.isdir(file_path)
    
    def posix_to_nfs4_perms(posix_perms: str, is_directory: bool = False) -> str:
        if posix_perms == '---':
            return ""
        
        # 使用最简单的权限映射
        perms = ""
        
        if 'r' in posix_perms:
            perms += 'r'  # read_data
        if 'w' in posix_perms:
            perms += 'w'  # write_data
        if 'x' in posix_perms:
            perms += 'x'  # execute
        
        return perms
    
    def is_valid_name(name: str) -> bool:
        if not name or name.isdigit():
            return False
        import string
        valid_chars = string.ascii_letters + string.digits + '_-'
        return all(c in valid_chars for c in name)
    
    print(f"\n转换为NFSv4 ACL (文件类型: {'目录' if is_dir else '文件'}):")
    
    # 处理用户ACL
    for user_acl in acl_entries.get('user', []):
        name = user_acl['name']
        perms = user_acl['perms']
        
        print(f"  用户 {name}: {perms}")
        
        if not is_valid_name(name):
            print(f"    ❌ 无效用户名: {name}")
            continue
            
        # 检查用户是否存在
        try:
            pwd.getpwnam(name)
            print(f"    ✓ 用户存在")
        except KeyError:
            print(f"    ⚠️  用户不存在: {name}")
        
        nfs4_perms = posix_to_nfs4_perms(perms, is_dir)
        if nfs4_perms:
            acl_entry = f"A::{name}:{nfs4_perms}"
            nfs4_acls.append(acl_entry)
            print(f"    → NFSv4: {acl_entry}")
        else:
            print(f"    → 跳过 (无权限)")
    
    # 处理组ACL
    for group_acl in acl_entries.get('group', []):
        name = group_acl['name']
        perms = group_acl['perms']
        
        print(f"  组 {name}: {perms}")
        
        if not is_valid_name(name):
            print(f"    ❌ 无效组名: {name}")
            continue
            
        # 检查组是否存在
        try:
            grp.getgrnam(name)
            print(f"    ✓ 组存在")
        except KeyError:
            print(f"    ⚠️  组不存在: {name}")
        
        nfs4_perms = posix_to_nfs4_perms(perms, is_dir)
        if nfs4_perms:
            acl_entry = f"A:g:{name}:{nfs4_perms}"
            nfs4_acls.append(acl_entry)
            print(f"    → NFSv4: {acl_entry}")
        else:
            print(f"    → 跳过 (无权限)")
    
    return nfs4_acls

def test_nfs4_acl(file_path: str, nfs4_acls: list):
    """测试NFSv4 ACL应用"""
    print(f"\n测试NFSv4 ACL应用到 {file_path}:")
    
    if not nfs4_acls:
        print("  没有ACL需要应用")
        return
    
    # 清除现有ACL
    result = subprocess.run(
        ['nfs4_setfacl', '-b', file_path],
        capture_output=True,
        text=True
    )
    
    if result.returncode != 0:
        print(f"  ❌ 清除ACL失败: {result.stderr}")
        return
    else:
        print("  ✓ 清除现有ACL成功")
    
    # 逐个应用ACL
    for acl in nfs4_acls:
        print(f"  应用: {acl}")
        result = subprocess.run(
            ['nfs4_setfacl', '-a', acl, file_path],
            capture_output=True,
            text=True
        )
        
        if result.returncode != 0:
            print(f"    ❌ 失败: {result.stderr}")
        else:
            print(f"    ✓ 成功")

def show_current_nfs4_acl(file_path: str):
    """显示当前NFSv4 ACL"""
    print(f"\n当前NFSv4 ACL:")
    result = subprocess.run(
        ['nfs4_getfacl', file_path],
        capture_output=True,
        text=True
    )
    
    if result.returncode == 0:
        print(result.stdout)
    else:
        print(f"获取NFSv4 ACL失败: {result.stderr}")

def main():
    if len(sys.argv) != 2:
        print("用法: python3 diagnose_acl.py <文件路径>")
        sys.exit(1)
    
    file_path = sys.argv[1]
    
    if not os.path.exists(file_path):
        print(f"文件不存在: {file_path}")
        sys.exit(1)
    
    print(f"诊断文件: {file_path}")
    print("=" * 60)
    
    # 获取POSIX ACL
    acl_entries = get_posix_acl(file_path)
    if not acl_entries:
        sys.exit(1)
    
    # 转换为NFSv4
    nfs4_acls = convert_to_nfs4(acl_entries, file_path)
    
    # 测试应用
    test_nfs4_acl(file_path, nfs4_acls)
    
    # 显示结果
    show_current_nfs4_acl(file_path)

if __name__ == '__main__':
    main()