#!/bin/bash

# Git历史清理脚本 - 删除2025年6月19日之前的所有提交

echo "开始清理Git历史记录..."

# 1. 创建备份分支
echo "步骤1: 创建备份分支..."
git branch backup-20241201-before-cleanup

# 2. 创建一个没有历史的新分支
echo "步骤2: 创建新的干净分支..."
git checkout --orphan new_clean_history

# 3. 添加所有当前文件
echo "步骤3: 添加所有文件..."
git add -A

# 4. 创建第一个干净的提交
echo "步骤4: 创建初始提交..."
git commit -m "feat: initialize clean repository

- Complete project codebase with all features
- Remove historical commits before 2025-06-19
- Maintain current project state and functionality

This is a fresh start with clean commit history while preserving all code."

# 5. 删除旧的main分支
echo "步骤5: 删除旧的main分支..."
git branch -D main

# 6. 重命名新分支为main
echo "步骤6: 重命名新分支为main..."
git branch -m main

# 7. 强制推送到远程仓库
echo "步骤7: 准备推送到远程仓库..."
echo "请手动执行: git push -f origin main"

echo "清理完成！"
echo "备份分支: backup-20241201-before-cleanup"
echo "如需恢复，执行: git checkout backup-20241201-before-cleanup"

