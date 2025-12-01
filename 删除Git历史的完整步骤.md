# 删除2025年6月19日之前的Git历史 - 完整执行步骤

## ⚠️ 重要提醒
- 此操作将**永久删除**所有旧的提交历史
- 已创建备份分支以防万一需要恢复
- 请在**新的终端窗口**中执行以下命令

## 📋 执行步骤

### 步骤1: 打开新终端并进入项目目录
```bash
cd /mnt/c/Users/HP/Desktop/Desktop/newgalaxyai/new_finance_ai
```

### 步骤2: 创建备份分支（非常重要！）
```bash
git branch backup-20241201-before-cleanup
```

### 步骤3: 创建没有历史的新分支
```bash
git checkout --orphan new_clean_history
```

### 步骤4: 添加所有当前文件
```bash
git add -A
```

### 步骤5: 创建第一个干净的提交
```bash
git commit -m "feat: initialize clean repository

- Complete project codebase with all features
- Remove historical commits before 2025-06-19
- Maintain current project state and functionality

This is a fresh start with clean commit history while preserving all code."
```

### 步骤6: 删除旧的main分支
```bash
git branch -D main
```

### 步骤7: 重命名新分支为main
```bash
git branch -m main
```

### 步骤8: 强制推送到远程仓库
```bash
git push -f origin main
```

### 步骤9: 清理本地引用（可选）
```bash
git gc --aggressive --prune=all
```

## 🔄 如果需要恢复旧历史

如果操作后需要恢复，执行：
```bash
git checkout backup-20241201-before-cleanup
git branch -D main
git branch -m main
git push -f origin main
```

## ✅ 验证结果

执行完成后，验证历史是否已清理：
```bash
# 查看提交历史（应该只有1个提交）
git log --oneline

# 查看所有分支
git branch -a
```

## 📊 预期结果

- ✅ 只有1个初始提交
- ✅ 所有代码文件保持不变
- ✅ 备份分支保留了完整历史
- ✅ 远程仓库历史已清理

## 🚨 团队协作提醒

如果有其他人也在使用这个仓库，他们需要：

1. 删除本地仓库
2. 重新克隆：
```bash
git clone <repository-url>
```

或者强制更新：
```bash
git fetch origin
git reset --hard origin/main
```

## 💾 一键执行脚本

如果想一次性执行所有步骤（除了推送），可以使用：
```bash
bash clean_git_history.sh
```

然后手动执行推送：
```bash
git push -f origin main
```
