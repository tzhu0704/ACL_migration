#!/usr/bin/env python3
"""
POSIX ACL to NFSv4 ACL Migration Tool
用于从 Lustre (POSIX ACL) 迁移到 FSx for NetApp ONTAP (NFSv4 ACL)
"""

import os
import sys
import subprocess
import logging
import argparse
import json
import re
import pwd
import grp
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
import sqlite3

class ACLMigrationTool:
    """POSIX ACL 到 NFSv4 ACL 迁移工具"""
    
    def __init__(self, source_dir: str, dest_dir: str, log_dir: str = "logs",
                 db_path: str = None, workers: int = 4, incremental: bool = False, 
                 migrate_ownership: bool = False, background: bool = False, debug: bool = False,
                 domain: str = None):
        self.source_dir = Path(source_dir).resolve()
        self.dest_dir = Path(dest_dir).resolve()
        self.log_dir = Path(log_dir)
        self.workers = workers
        self.incremental = incremental
        self.migrate_ownership = migrate_ownership
        self.background = background
        self.debug = debug
        self.domain = domain
        
        # 创建日志目录
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        # 设置日志
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = self.log_dir / f"acl_migration_{timestamp}.log"
        
        # 后台模式只输出到文件
        handlers = [logging.FileHandler(log_file)]
        if not self.background:
            handlers.append(logging.StreamHandler(sys.stdout))
            
        log_level = logging.DEBUG if self.debug else logging.INFO
        logging.basicConfig(
            level=log_level,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=handlers
        )
        self.logger = logging.getLogger(__name__)
        
        # 数据库用于增量迁移
        if db_path is None:
            db_path = self.log_dir / "acl_migration.db"
        self.db_path = db_path
        self._init_database()
        
        # 统计信息
        self.stats = {
            'total_files': 0,
            'success': 0,
            'failed': 0,
            'skipped': 0,
            'no_acl': 0
        }
        
    def _init_database(self):
        """初始化数据库用于增量迁移"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS migrated_files (
                source_path TEXT PRIMARY KEY,
                dest_path TEXT,
                mtime REAL,
                acl_hash TEXT,
                migrated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                status TEXT
            )
        ''')
        conn.commit()
        conn.close()
    
    def reset_database(self):
        """重置数据库，清除所有迁移记录"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('DELETE FROM migrated_files')
            conn.commit()
            conn.close()
            self.logger.info(f"数据库已重置: {self.db_path}")
            return True
        except Exception as e:
            self.logger.error(f"重置数据库失败: {str(e)}")
            return False
    
    def show_database_stats(self):
        """显示数据库统计信息"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # 总记录数
            cursor.execute('SELECT COUNT(*) FROM migrated_files')
            total_count = cursor.fetchone()[0]
            
            # 按状态统计
            cursor.execute('SELECT status, COUNT(*) FROM migrated_files GROUP BY status')
            status_counts = cursor.fetchall()
            
            conn.close()
            
            print(f"数据库统计信息: {self.db_path}")
            print("=" * 50)
            print(f"总记录数: {total_count}")
            for status, count in status_counts:
                print(f"{status}: {count}")
            print("=" * 50)
            
        except Exception as e:
            print(f"获取数据库统计失败: {str(e)}")
        
    def _is_already_migrated(self, source_path: str, mtime: float) -> bool:
        """检查文件是否已经迁移过"""
        if not self.incremental:
            return False
            
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            'SELECT mtime, status FROM migrated_files WHERE source_path = ?',
            (source_path,)
        )
        result = cursor.fetchone()
        conn.close()
        
        if result and result[1] == 'success':
            stored_mtime = result[0]
            if abs(stored_mtime - mtime) < 0.001:
                return True
        return False
        
    def _record_migration(self, source_path: str, dest_path: str, 
                         mtime: float, acl_hash: str, status: str):
        """记录迁移状态"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO migrated_files 
            (source_path, dest_path, mtime, acl_hash, status)
            VALUES (?, ?, ?, ?, ?)
        ''', (source_path, dest_path, mtime, acl_hash, status))
        conn.commit()
        conn.close()
        
    def get_posix_acl(self, file_path: str) -> Optional[Dict]:
        """获取文件的 POSIX ACL 和所有权信息"""
        try:
            # 获取ACL信息
            result = subprocess.run(
                ['getfacl', '--absolute-names', '--omit-header', file_path],
                capture_output=True,
                text=True,
                check=True
            )
            
            # 获取文件所有权信息
            stat_info = os.stat(file_path)
            try:
                owner_name = pwd.getpwuid(stat_info.st_uid).pw_name
            except KeyError:
                owner_name = str(stat_info.st_uid)
            try:
                group_name = grp.getgrgid(stat_info.st_gid).gr_name
            except KeyError:
                group_name = str(stat_info.st_gid)
            
            acl_entries = {
                'owner': {'name': owner_name, 'perms': None},
                'group_owner': {'name': group_name, 'perms': None},
                'user': [],
                'group': [],
                'mask': None,
                'other': None
            }
            
            for line in result.stdout.strip().split('\n'):
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                    
                match = re.match(r'(user|group|mask|other):([^:]*):([rwx-]+)', line)
                if match:
                    acl_type, name, perms = match.groups()
                    
                    if acl_type == 'user':
                        if name == '':
                            # 文件所有者权限
                            acl_entries['owner']['perms'] = perms
                        else:
                            # 扩展用户ACL
                            acl_entries['user'].append({'name': name, 'perms': perms})
                    elif acl_type == 'group':
                        if name == '':
                            # 文件组所有者权限
                            acl_entries['group_owner']['perms'] = perms
                        else:
                            # 扩展组ACL
                            acl_entries['group'].append({'name': name, 'perms': perms})
                    elif acl_type == 'mask':
                        acl_entries['mask'] = perms
                    elif acl_type == 'other':
                        acl_entries['other'] = perms
                        
            return acl_entries
            
        except subprocess.CalledProcessError as e:
            self.logger.error(f"获取 POSIX ACL 失败 {file_path}: {e.stderr}")
            return None
        except Exception as e:
            self.logger.error(f"解析 POSIX ACL 失败 {file_path}: {str(e)}")
            return None
            
    def convert_posix_to_nfs4(self, posix_acl: Dict, file_path: str) -> List[str]:
        """将 POSIX ACL 转换为 NFSv4 ACL 命令"""
        nfs4_acls = []
        is_dir = os.path.isdir(file_path)
        
        def posix_to_nfs4_perms(posix_perms: str, is_directory: bool = False) -> str:
            """
            简化权限映射，与测试脚本保持一致
            """
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
            """检查用户名或组名是否有效"""
            if not name or name.isdigit():
                return False
            # 检查是否包含特殊字符
            import string
            valid_chars = string.ascii_letters + string.digits + '_-'
            return all(c in valid_chars for c in name)
        
        # 只处理扩展ACL，不处理文件所有者和组所有者
        # 添加扩展用户ACL
        for user_acl in posix_acl.get('user', []):
            name = user_acl['name']
            perms = user_acl['perms']
            
            if not is_valid_name(name):
                self.logger.warning(f"跳过无效用户名: {name}")
                continue
                
            # 添加域名后缀（如果提供）
            full_name = f"{name}@{self.domain}" if self.domain else name
                
            nfs4_perms = posix_to_nfs4_perms(perms, is_dir)
            if nfs4_perms:  # 只添加非空权限
                acl_entry = f"A::{full_name}:{nfs4_perms}"
                self.logger.debug(f"生成用户ACL: {name}:{perms} -> {acl_entry}")
                nfs4_acls.append(acl_entry)
            
        # 添加扩展组ACL
        for group_acl in posix_acl.get('group', []):
            name = group_acl['name']
            perms = group_acl['perms']
            
            if not is_valid_name(name):
                self.logger.warning(f"跳过无效组名: {name}")
                continue
                
            # 添加域名后缀（如果提供）
            full_name = f"{name}@{self.domain}" if self.domain else name
                
            nfs4_perms = posix_to_nfs4_perms(perms, is_dir)
            if nfs4_perms:  # 只添加非空权限
                acl_entry = f"A:g:{full_name}:{nfs4_perms}"
                self.logger.debug(f"生成组ACL: {name}:{perms} -> {acl_entry}")
                nfs4_acls.append(acl_entry)
            
        return nfs4_acls
        
    def apply_nfs4_acl(self, file_path: str, nfs4_acls: List[str]) -> bool:
        """应用 NFSv4 ACL 到目标文件"""
        try:
            if not nfs4_acls:
                return True  # 没有ACL需要应用
            
            # 验证ACL条目格式
            for acl in nfs4_acls:
                if not self._validate_nfs4_acl(acl):
                    self.logger.error(f"无效的NFSv4 ACL格式: {acl}")
                    return False
            
            # 不清除现有ACL，直接添加新的ACL条目
            return self._apply_acl_individually(file_path, nfs4_acls)
                    
            return True
            
        except Exception as e:
            self.logger.error(f"应用 NFSv4 ACL 异常 {file_path}: {str(e)}")
            return False
    
    def _validate_nfs4_acl(self, acl: str) -> bool:
        """验证NFSv4 ACL条目格式"""
        import re
        # NFSv4 ACL格式: [A|D]:[flags]:[principal]:[permissions]
        # 根据你的示例: A:g:dev0_test1@mpdemo1.example.com:rwaDxtTnNcy
        pattern = r'^[AD]:[fg]?:[^:]*:[rwaDxtTnNcy]*$'
        return bool(re.match(pattern, acl))
    
    def _apply_acl_individually(self, file_path: str, nfs4_acls: List[str]) -> bool:
        """逐个应用ACL条目"""
        for acl in nfs4_acls:
            self.logger.debug(f"单独应用ACL: {acl} 到 {file_path}")
            
            result = subprocess.run(
                ['nfs4_setfacl', '-a', acl, file_path],
                capture_output=True,
                text=True
            )
            
            if result.returncode != 0:
                error_msg = result.stderr.strip()
                self.logger.error(f"应用 NFSv4 ACL 失败 {file_path}: {error_msg}")
                self.logger.error(f"失败的ACL条目: {acl}")
                return False
                
        return True
            
    def migrate_file_ownership(self, source_file: Path, dest_file: Path) -> bool:
        """迁移文件所有权"""
        try:
            source_stat = source_file.stat()
            dest_stat = dest_file.stat()
            
            # 检查是否需要更改所有权
            if source_stat.st_uid == dest_stat.st_uid and source_stat.st_gid == dest_stat.st_gid:
                self.logger.debug(f"所有权已匹配，无需更改: {dest_file}")
                return True
            
            # 获取源文件的用户名和组名
            try:
                owner_name = pwd.getpwuid(source_stat.st_uid).pw_name
            except KeyError:
                self.logger.warning(f"无法找到UID {source_stat.st_uid} 对应的用户名，使用数字ID")
                owner_name = str(source_stat.st_uid)
            
            try:
                group_name = grp.getgrgid(source_stat.st_gid).gr_name
            except KeyError:
                self.logger.warning(f"无法找到GID {source_stat.st_gid} 对应的组名，使用数字ID")
                group_name = str(source_stat.st_gid)
            
            self.logger.debug(f"迁移所有权: {dest_file} -> {owner_name}:{group_name}")
            
            # 使用 chown 命令设置所有权（使用用户名:组名格式）
            result = subprocess.run(
                ['chown', f'{owner_name}:{group_name}', str(dest_file)],
                capture_output=True,
                text=True
            )
            
            if result.returncode != 0:
                self.logger.error(f"设置文件所有权失败 {dest_file}: {result.stderr}")
                self.logger.error(f"尝试的所有权: {owner_name}:{group_name}")
                return False
            
            self.logger.debug(f"成功设置所有权: {dest_file} -> {owner_name}:{group_name}")
            return True
            
        except Exception as e:
            self.logger.error(f"迁移文件所有权异常 {dest_file}: {str(e)}")
            return False
    
    def migrate_file_acl(self, source_file: Path) -> Tuple[str, bool, str]:
        """迁移单个文件的所有权和 ACL"""
        try:
            # 处理单文件和目录模式
            if self.source_dir.is_file():
                # 单文件模式：直接使用目标路径
                dest_file = self.dest_dir
            else:
                # 目录模式：计算相对路径
                rel_path = source_file.relative_to(self.source_dir)
                dest_file = self.dest_dir / rel_path
            
            if not dest_file.exists():
                return (str(source_file), False, "目标文件不存在")
                
            source_mtime = source_file.stat().st_mtime
            if self._is_already_migrated(str(source_file), source_mtime):
                return (str(source_file), True, "已迁移(跳过)")
            
            # 1. 迁移文件所有权
            ownership_success = True
            if self.migrate_ownership:
                ownership_success = self.migrate_file_ownership(source_file, dest_file)
            
            # 2. 迁移 ACL
            posix_acl = self.get_posix_acl(str(source_file))
            acl_success = True
            acl_count = 0
            
            if posix_acl is not None:
                nfs4_acls = self.convert_posix_to_nfs4(posix_acl, str(source_file))
                if nfs4_acls:
                    acl_success = self.apply_nfs4_acl(str(dest_file), nfs4_acls)
                    acl_count = len(nfs4_acls)
            
            # 记录迁移状态
            acl_hash = json.dumps(posix_acl, sort_keys=True) if posix_acl else ""
            overall_success = ownership_success and acl_success
            status = "success" if overall_success else "failed"
            
            self._record_migration(
                str(source_file), str(dest_file),
                source_mtime, acl_hash, status
            )
            
            # 生成结果消息
            messages = []
            if self.migrate_ownership and ownership_success:
                messages.append("所有权")
            if acl_count > 0 and acl_success:
                messages.append(f"{acl_count}个ACL条目")
            
            if overall_success:
                if messages:
                    return (str(source_file), True, f"成功迁移: {', '.join(messages)}")
                else:
                    return (str(source_file), True, "无需迁移")
            else:
                failed_items = []
                if self.migrate_ownership and not ownership_success:
                    failed_items.append("所有权")
                if not acl_success:
                    failed_items.append("ACL")
                return (str(source_file), False, f"迁移失败: {', '.join(failed_items)}")
                
        except Exception as e:
            self.logger.error(f"迁移文件异常 {source_file}: {str(e)}")
            return (str(source_file), False, str(e))
            
    def scan_files(self) -> List[Path]:
        """扫描源路径（支持单文件和目录）"""
        files = []
        
        if self.source_dir.is_file():
            # 单文件模式
            self.logger.info(f"单文件模式: {self.source_dir}")
            files.append(self.source_dir)
        elif self.source_dir.is_dir():
            # 目录模式
            self.logger.info(f"扫描源目录: {self.source_dir}")
            for root, dirs, filenames in os.walk(self.source_dir):
                root_path = Path(root)
                
                for dirname in dirs:
                    dir_path = root_path / dirname
                    files.append(dir_path)
                    
                for filename in filenames:
                    file_path = root_path / filename
                    files.append(file_path)
        else:
            raise ValueError(f"源路径不存在或不是文件/目录: {self.source_dir}")
                
        self.logger.info(f"找到 {len(files)} 个文件/目录")
        return files
        
    def migrate(self):
        """执行迁移"""
        self.logger.info("=" * 80)
        self.logger.info("开始文件所有权和 POSIX ACL 到 NFSv4 ACL 迁移")
        self.logger.info(f"源目录: {self.source_dir}")
        self.logger.info(f"目标目录: {self.dest_dir}")
        self.logger.info(f"并发数: {self.workers}")
        self.logger.info(f"增量模式: {self.incremental}")
        self.logger.info("=" * 80)
        
        files = self.scan_files()
        self.stats['total_files'] = len(files)
        
        with ThreadPoolExecutor(max_workers=self.workers) as executor:
            futures = {
                executor.submit(self.migrate_file_acl, f): f 
                for f in files
            }
            
            for future in as_completed(futures):
                file_path, success, message = future.result()
                
                if "已迁移(跳过)" in message:
                    self.stats['skipped'] += 1
                    self.logger.debug(f"跳过: {file_path}")
                elif "无扩展ACL" in message:
                    self.stats['no_acl'] += 1
                    self.logger.debug(f"无ACL: {file_path}")
                elif success:
                    self.stats['success'] += 1
                    self.logger.info(f"成功: {file_path} - {message}")
                else:
                    self.stats['failed'] += 1
                    self.logger.error(f"失败: {file_path} - {message}")
                    
        self.print_summary()
        
    def print_summary(self):
        """打印迁移摘要"""
        self.logger.info("=" * 80)
        self.logger.info("迁移完成 - 统计信息")
        self.logger.info("=" * 80)
        self.logger.info(f"总文件数: {self.stats['total_files']}")
        self.logger.info(f"成功迁移: {self.stats['success']}")
        self.logger.info(f"失败: {self.stats['failed']}")
        self.logger.info(f"跳过(已迁移): {self.stats['skipped']}")
        self.logger.info(f"无扩展ACL: {self.stats['no_acl']}")
        self.logger.info("=" * 80)
        self.logger.info(f"日志目录: {self.log_dir}")
        self.logger.info(f"数据库: {self.db_path}")
        self.logger.info("=" * 80)

def main():
    parser = argparse.ArgumentParser(
        description='文件所有权和 POSIX ACL 到 NFSv4 ACL 迁移工具',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 基本用法
  %(prog)s -s /mnt/lustre/data -d /mnt/netapp/data
  
  # 增量迁移
  %(prog)s -s /mnt/lustre/data -d /mnt/netapp/data --incremental
  
  # 指定并发数
  %(prog)s -s /mnt/lustre/data -d /mnt/netapp/data -w 8
        """
    )
    
    parser.add_argument('-s', '--source', help='源路径 (文件或目录, POSIX ACL)')
    parser.add_argument('-d', '--dest', help='目标路径 (文件或目录, NFSv4 ACL)')
    parser.add_argument('-l', '--log-dir', default='logs', help='日志目录')
    parser.add_argument('-w', '--workers', type=int, default=4, help='并发线程数')
    parser.add_argument('--incremental', action='store_true', help='增量模式')
    parser.add_argument('--ownership', action='store_true', help='迁移文件所有权')
    parser.add_argument('-b', '--background', action='store_true', help='后台运行模式')
    parser.add_argument('--debug', action='store_true', help='启用调试模式')
    parser.add_argument('--domain', help='NFSv4域名后缀 (例: mpdemo1.example.com)')
    parser.add_argument('--db', help='数据库路径')
    parser.add_argument('--reset-db', action='store_true', help='重置数据库，清除所有迁移记录')
    parser.add_argument('--show-db-stats', action='store_true', help='显示数据库统计信息')
    
    args = parser.parse_args()
    
    # 检查必需参数
    if not (args.reset_db or args.show_db_stats):
        if not args.source:
            parser.error('非数据库操作需要 -s/--source 参数')
        if not args.dest:
            parser.error('非数据库操作需要 -d/--dest 参数')
    
    # 数据库操作模式，使用默认值
    if args.reset_db or args.show_db_stats:
        args.source = args.source or '/tmp'
        args.dest = args.dest or '/tmp'
    else:
        # 检查源路径
        if not os.path.exists(args.source):
            print(f"错误: 源路径不存在: {args.source}")
            sys.exit(1)
        
        # 检查目标路径
        if os.path.isfile(args.source):
            # 单文件模式：目标必须是文件
            if not os.path.isfile(args.dest):
                print(f"错误: 单文件模式下，目标必须是文件: {args.dest}")
                sys.exit(1)
        else:
            # 目录模式：目标必须是目录
            if not os.path.isdir(args.dest):
                print(f"错误: 目录模式下，目标必须是目录: {args.dest}")
                sys.exit(1)
        
    tool = ACLMigrationTool(
        source_dir=args.source,
        dest_dir=args.dest,
        log_dir=args.log_dir,
        db_path=args.db,
        workers=args.workers,
        incremental=args.incremental,
        migrate_ownership=args.ownership,
        background=args.background,
        debug=args.debug,
        domain=args.domain
    )
    
    try:
        # 处理数据库操作
        if args.reset_db:
            if tool.reset_database():
                print("数据库重置成功")
            else:
                print("数据库重置失败")
                sys.exit(1)
            return
        
        if args.show_db_stats:
            tool.show_database_stats()
            return
        
        # 执行迁移
        tool.migrate()
    except KeyboardInterrupt:
        print("\n迁移被用户中断")
        sys.exit(1)
    except Exception as e:
        print(f"迁移失败: {str(e)}")
        sys.exit(1)

if __name__ == '__main__':
    main()
