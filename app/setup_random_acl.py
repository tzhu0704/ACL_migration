#!/usr/bin/env python3
"""
Random POSIX ACL Setup Tool
为源目录的文件随机设置POSIX ACL
"""

import os
import sys
import subprocess
import random
import argparse
from pathlib import Path

class RandomACLSetup:
    """随机POSIX ACL设置工具"""
    
    def __init__(self, target_dir: str, percentage: int = 50):
        self.target_dir = Path(target_dir).resolve()
        self.percentage = percentage
        
        # 预定义用户和组
        all_users = ['tzhu', 'mary', 'bob', 'peter', 'john', 'laura', 'demouser1', 'demouser2', 'demouser3']
        all_groups = ['wlogins', 'dev1', 'dev0_test1', 'dev0']
        
        # 检查系统中存在的用户和组
        self.users = self._get_existing_users(all_users)
        self.groups = self._get_existing_groups(all_groups)
        
        if not self.users:
            print("警告: 没有找到预定义的用户，将使用当前用户")
            import getpass
            self.users = [getpass.getuser()]
        
        if not self.groups:
            print("警告: 没有找到预定义的组，将使用当前用户的主组")
            import grp, os
            try:
                gid = os.getgid()
                group_name = grp.getgrgid(gid).gr_name
                self.groups = [group_name]
            except:
                self.groups = ['users']  # 默认组
        
        # 权限组合
        self.permissions = ['r--', 'rw-', 'r-x', 'rwx', '-wx', '--x']
        
        self.stats = {
            'total_files': 0,
            'processed': 0,
            'skipped': 0,
            'failed': 0
        }
    
    def generate_random_acl(self) -> list:
        """生成随机ACL条目"""
        acl_entries = []
        
        # 随机选择1-3个用户
        num_users = random.randint(1, 3)
        selected_users = random.sample(self.users, num_users)
        
        for user in selected_users:
            perm = random.choice(self.permissions)
            acl_entries.append(f"user:{user}:{perm}")
        
        # 随机选择1-2个组
        num_groups = random.randint(1, 2)
        selected_groups = random.sample(self.groups, num_groups)
        
        for group in selected_groups:
            perm = random.choice(self.permissions)
            acl_entries.append(f"group:{group}:{perm}")
        
        return acl_entries
    
    def _get_existing_users(self, user_list: list) -> list:
        """检查系统中存在的用户"""
        import pwd
        existing_users = []
        for user in user_list:
            try:
                pwd.getpwnam(user)
                existing_users.append(user)
            except KeyError:
                pass
        return existing_users
    
    def _get_existing_groups(self, group_list: list) -> list:
        """检查系统中存在的组"""
        import grp
        existing_groups = []
        for group in group_list:
            try:
                grp.getgrnam(group)
                existing_groups.append(group)
            except KeyError:
                pass
        return existing_groups
    
    def apply_acl(self, file_path: Path, acl_entries: list) -> bool:
        """应用ACL到文件"""
        try:
            # 构建setfacl命令
            cmd = ['setfacl', '-m', ','.join(acl_entries), str(file_path)]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode != 0:
                error_msg = result.stderr.strip()
                if "Operation not permitted" in error_msg:
                    print(f"权限不足 {file_path}: 需要sudo权限或文件所有者权限")
                elif "Invalid argument" in error_msg:
                    print(f"无效参数 {file_path}: 用户或组可能不存在")
                else:
                    print(f"设置ACL失败 {file_path}: {error_msg}")
                return False
            
            return True
            
        except Exception as e:
            print(f"应用ACL异常 {file_path}: {str(e)}")
            return False
    
    def scan_and_process(self):
        """扫描并处理文件"""
        print(f"扫描目录: {self.target_dir}")
        files = []
        
        for root, dirs, filenames in os.walk(self.target_dir):
            root_path = Path(root)
            
            # 处理目录
            for dirname in dirs:
                dir_path = root_path / dirname
                files.append(dir_path)
            
            # 处理文件
            for filename in filenames:
                file_path = root_path / filename
                files.append(file_path)
        
        self.stats['total_files'] = len(files)
        print(f"找到 {len(files)} 个文件/目录")
        
        # 随机处理指定百分比的文件
        num_to_process = int(len(files) * self.percentage / 100)
        files_to_process = random.sample(files, num_to_process)
        
        print(f"将为 {len(files_to_process)} 个文件设置随机ACL ({self.percentage}%)")
        print(f"可用用户: {', '.join(self.users)}")
        print(f"可用组: {', '.join(self.groups)}")
        print()
        
        for file_path in files_to_process:
            if random.random() * 100 < self.percentage:
                acl_entries = self.generate_random_acl()
                
                print(f"设置ACL: {file_path}")
                print(f"  ACL: {', '.join(acl_entries)}")
                
                if self.apply_acl(file_path, acl_entries):
                    self.stats['processed'] += 1
                else:
                    self.stats['failed'] += 1
            else:
                self.stats['skipped'] += 1
    
    def print_summary(self):
        """打印统计摘要"""
        print("=" * 60)
        print("随机ACL设置完成 - 统计信息")
        print("=" * 60)
        print(f"总文件数: {self.stats['total_files']}")
        print(f"已处理: {self.stats['processed']}")
        print(f"跳过: {self.stats['skipped']}")
        print(f"失败: {self.stats['failed']}")
        print("=" * 60)

def main():
    parser = argparse.ArgumentParser(
        description='随机POSIX ACL设置工具',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 为50%的文件设置随机ACL
  %(prog)s -d /path/to/directory
  
  # 为80%的文件设置随机ACL
  %(prog)s -d /path/to/directory -p 80
  
用户: tzhu, mary, bob, peter, john, laura, demouser1, demouser2, demouser3
组: wlogins, dev1, dev0_test1, dev0
        """
    )
    
    parser.add_argument('-d', '--directory', required=True, help='目标目录路径')
    parser.add_argument('-p', '--percentage', type=int, default=50, 
                       help='处理文件的百分比 (默认: 50)')
    
    args = parser.parse_args()
    
    if not os.path.isdir(args.directory):
        print(f"错误: 目录不存在: {args.directory}")
        sys.exit(1)
    
    if not (1 <= args.percentage <= 100):
        print(f"错误: 百分比必须在1-100之间: {args.percentage}")
        sys.exit(1)
    
    # 检查setfacl命令
    try:
        subprocess.run(['setfacl', '--version'], capture_output=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("错误: setfacl 命令不可用，请安装 acl 包")
        sys.exit(1)
    
    tool = RandomACLSetup(args.directory, args.percentage)
    
    try:
        tool.scan_and_process()
        tool.print_summary()
    except KeyboardInterrupt:
        print("\n操作被用户中断")
        sys.exit(1)
    except Exception as e:
        print(f"操作失败: {str(e)}")
        sys.exit(1)

if __name__ == '__main__':
    main()