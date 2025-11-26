#!/usr/bin/env python3
"""
测试NFSv4权限映射
"""

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

def test_permissions():
    test_cases = [
        ('r--', False),
        ('rw-', False),
        ('r-x', False),
        ('rwx', False),
        ('-wx', False),
        ('--x', False),
        ('---', False),
        ('rwx', True),  # 目录
        ('rw-', True),  # 目录
    ]
    
    print("POSIX权限 -> NFSv4权限 映射测试:")
    print("=" * 50)
    
    for posix_perm, is_dir in test_cases:
        nfs4_perm = posix_to_nfs4_perms(posix_perm, is_dir)
        file_type = "目录" if is_dir else "文件"
        print(f"{posix_perm} ({file_type}) -> {nfs4_perm}")
    
    print("\n生成的ACL条目示例:")
    print("=" * 50)
    
    users = ['peter', 'mary', 'bob']
    groups = ['dev1', 'wlogins']
    
    for user in users:
        nfs4_perm = posix_to_nfs4_perms('rwx', False)
        print(f"A::{user}@mpdemo1.example.com:{nfs4_perm}")
    
    for group in groups:
        nfs4_perm = posix_to_nfs4_perms('rw-', False)
        print(f"A:g:{group}@mpdemo1.example.com:{nfs4_perm}")

if __name__ == '__main__':
    test_permissions()