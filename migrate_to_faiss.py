#!/usr/bin/env python3
"""
Dify到FAISS向量数据库的数据迁移脚本

使用方法:
python migrate_to_faiss.py [--force] [--dry-run]

参数说明:
--force: 强制覆盖已存在的向量数据库
--dry-run: 只预览要迁移的数据，不实际执行迁移
"""

import sys
import os
import argparse
import asyncio
from datetime import datetime
from typing import Dict, List, Optional

from logger import task_logger
from models.database import PostsDB
from services.vector_service import DocumentManager
from tqdm import tqdm


class DifyToFaissMigrator:
    """Dify到FAISS的数据迁移器"""
    
    def __init__(self):
        self.posts_db = PostsDB()
        self.doc_manager = DocumentManager()
        self.migration_stats = {
            "total_posts": 0,
            "migrated_posts": 0,
            "failed_posts": 0,
            "skipped_posts": 0
        }
    
    async def get_migration_data(self) -> Dict[str, List]:
        """获取需要迁移的数据"""
        TYPE_MAP = {
            "Zaokan": "早间必读",
            "Fupan": "逻辑复盘",
            "Essence": "精华内容"
        }
        
        migration_data = {
            "早间必读": [],
            "逻辑复盘": [],
            "精华内容": []
        }
        
        task_logger.info("正在获取迁移数据...")
        
        for type_key, type_name in TYPE_MAP.items():
            try:
                posts = await self.posts_db.get_posts(type=type_key, limit=None)
                migration_data[type_name] = posts
                task_logger.info(f"获取到 {len(posts)} 篇 {type_name} 文章")
            except Exception as e:
                task_logger.error(f"获取 {type_name} 数据失败: {str(e)}")
                migration_data[type_name] = []
        
        return migration_data
    
    def preview_migration(self, migration_data: Dict[str, List]) -> None:
        """预览迁移数据"""
        print("\n" + "="*60)
        print("📊 数据迁移预览")
        print("="*60)
        
        total_count = 0
        for post_type, posts in migration_data.items():
            count = len(posts)
            total_count += count
            print(f"📑 {post_type}: {count} 篇文章")
            
            if posts:
                # 显示最新和最旧的文章信息
                latest_post = max(posts, key=lambda x: x.get('time', 0))
                oldest_post = min(posts, key=lambda x: x.get('time', 0))
                
                latest_date = datetime.fromtimestamp(latest_post.get('time', 0)).strftime('%Y-%m-%d')
                oldest_date = datetime.fromtimestamp(oldest_post.get('time', 0)).strftime('%Y-%m-%d')
                
                print(f"   📅 时间范围: {oldest_date} ~ {latest_date}")
                print(f"   📋 最新文章: {latest_post.get('title', '无标题')[:50]}...")
        
        print(f"\n📊 总计: {total_count} 篇文章需要迁移")
        print("="*60)
    
    async def migrate_posts(self, migration_data: Dict[str, List], dry_run: bool = False) -> bool:
        """迁移文章数据"""
        if dry_run:
            self.preview_migration(migration_data)
            return True
        
        try:
            # 检查向量数据库是否已存在
            if self.doc_manager.vector_service.index_exists() and not self.confirm_overwrite():
                print("❌ 迁移已取消")
                return False
            
            # 开始迁移
            task_logger.info("开始迁移数据到FAISS向量数据库...")
            
            all_posts = []
            for post_type, posts in migration_data.items():
                for post in posts:
                    post['type'] = post_type  # 添加类型标记
                    all_posts.append(post)
            
            self.migration_stats["total_posts"] = len(all_posts)
            
            # 批量处理文章
            batch_size = 50
            failed_posts = []
            
            with tqdm(total=len(all_posts), desc="迁移进度") as pbar:
                for i in range(0, len(all_posts), batch_size):
                    batch = all_posts[i:i + batch_size]
                    
                    for post in batch:
                        try:
                            success = await self.migrate_single_post(post)
                            if success:
                                self.migration_stats["migrated_posts"] += 1
                            else:
                                self.migration_stats["failed_posts"] += 1
                                failed_posts.append(post)
                        except Exception as e:
                            task_logger.error(f"迁移文章失败: {post.get('md5', 'unknown')} - {str(e)}")
                            self.migration_stats["failed_posts"] += 1
                            failed_posts.append(post)
                        
                        pbar.update(1)
            
            # 保存向量数据库
            task_logger.info("正在保存向量数据库...")
            self.doc_manager.vector_service.save_index()
            
            # 输出迁移统计
            self.print_migration_stats(failed_posts)
            
            return self.migration_stats["failed_posts"] == 0
            
        except Exception as e:
            task_logger.error(f"迁移过程中发生错误: {str(e)}")
            return False
    
    async def migrate_single_post(self, post: Dict) -> bool:
        """迁移单篇文章"""
        try:
            # 检查是否已经存在
            if self.doc_manager.document_exists(post.get('md5', '')):
                self.migration_stats["skipped_posts"] += 1
                return True
            
            # 构造文档元数据
            metadata = {
                "type": post.get('type', '未知类型'),
                "date": post.get('time', 0),
                "md5": post.get('md5', ''),
                "title": post.get('title', ''),
                "source": "migration_from_dify"
            }
            
            # 添加文档到向量数据库
            success = self.doc_manager.add_document(
                doc_id=post.get('md5', ''),
                content=post.get('mes', ''),
                metadata=metadata,
                save_immediately=False  # 批量保存
            )
            
            return success
            
        except Exception as e:
            task_logger.error(f"迁移单篇文章失败: {str(e)}")
            return False
    
    def confirm_overwrite(self) -> bool:
        """确认是否覆盖已存在的数据"""
        print("\n⚠️  检测到已存在的向量数据库")
        print("继续操作将会覆盖现有数据。")
        
        while True:
            choice = input("是否继续? (y/n): ").lower().strip()
            if choice in ['y', 'yes']:
                return True
            elif choice in ['n', 'no']:
                return False
            else:
                print("请输入 y 或 n")
    
    def print_migration_stats(self, failed_posts: List[Dict]) -> None:
        """打印迁移统计信息"""
        print("\n" + "="*60)
        print("🎉 数据迁移完成!")
        print("="*60)
        print(f"📊 总计文章: {self.migration_stats['total_posts']}")
        print(f"✅ 成功迁移: {self.migration_stats['migrated_posts']}")
        print(f"⚠️  跳过重复: {self.migration_stats['skipped_posts']}")
        print(f"❌ 迁移失败: {self.migration_stats['failed_posts']}")
        
        if failed_posts:
            print(f"\n❌ 失败的文章:")
            for post in failed_posts[:10]:  # 只显示前10个
                print(f"   - {post.get('title', '无标题')[:50]}... (MD5: {post.get('md5', 'unknown')})")
            
            if len(failed_posts) > 10:
                print(f"   ... 还有 {len(failed_posts) - 10} 个失败项目")
        
        print("="*60)
        
        # 输出向量数据库统计
        vector_stats = self.doc_manager.vector_service.get_stats()
        print(f"🔍 向量数据库统计:")
        print(f"   📄 文档总数: {vector_stats['total_documents']}")
        print(f"   🧩 分块总数: {vector_stats['total_chunks']}")
        print(f"   💾 索引大小: {vector_stats['index_size']}")
        print("="*60)


async def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="将Dify知识库数据迁移到FAISS向量数据库",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例用法:
    python migrate_to_faiss.py --dry-run     # 预览迁移数据
    python migrate_to_faiss.py               # 执行迁移
    python migrate_to_faiss.py --force       # 强制覆盖现有数据
        """
    )
    
    parser.add_argument(
        '--dry-run', 
        action='store_true', 
        help='只预览要迁移的数据，不实际执行迁移'
    )
    
    parser.add_argument(
        '--force', 
        action='store_true', 
        help='强制覆盖已存在的向量数据库'
    )
    
    args = parser.parse_args()
    
    # 创建迁移器
    migrator = DifyToFaissMigrator()
    
    try:
        print("🚀 开始数据迁移流程...")
        
        # 获取迁移数据
        migration_data = await migrator.get_migration_data()
        
        if not any(migration_data.values()):
            print("❌ 没有找到可迁移的数据")
            return
        
        # 如果是强制模式，自动覆盖
        if args.force:
            if migrator.doc_manager.vector_service.index_exists():
                print("🗑️  强制模式: 清理现有向量数据库...")
                migrator.doc_manager.vector_service.clear_all()
        
        # 执行迁移
        success = await migrator.migrate_posts(migration_data, dry_run=args.dry_run)
        
        if success:
            if not args.dry_run:
                print("✅ 迁移成功完成!")
                print("\n🔄 现在可以停止并重启应用以使用新的向量数据库。")
            else:
                print("👀 预览完成。使用 --force 参数执行实际迁移。")
        else:
            print("❌ 迁移过程中出现错误")
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\n🛑 迁移被用户中断")
        sys.exit(1)
    except Exception as e:
        print(f"❌ 迁移失败: {str(e)}")
        task_logger.error(f"迁移失败: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main()) 