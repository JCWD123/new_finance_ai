#!/bin/bash

# 增强版智能仓库重定向脚本
# 使用方式：./redirect_repos.sh [项目根目录]
# 示例：./redirect_repos.sh ~/projects  # 处理所有子目录中的项目

# 配置新的仓库域名
NEW_DOMAIN="github.com"
ORG_NAME="JCWD123"  # 你的 GitHub 用户名/组织名

# 标准的忽略规则
STANDARD_IGNORE_RULES=(
    "# IDE files"
    ".idea/"
    ".vscode/"
    "*.code-workspace"

    "# Python compiled files"
    "__pycache__/"
    "*.py[cod]"
    "*.pyc"
    "*.pyo"
    "*.pyd"

    "# Jupyter Notebook checkpoints"
    ".ipynb_checkpoints/"

    "# Log files"
    "logs/"
    "*.log"

    "# Environment variables"
    ".env"
    ".env.local"
    ".secret"

    "# OS generated files"
    ".DS_Store"
    "Thumbs.db"

    "# Coverage files"
    ".coverage"
    "htmlcov/"
)

# 更新 .gitignore 文件
update_gitignore() {
    local gitignore_path="$1/.gitignore"

    # 如果 .gitignore 不存在则创建
    if [ ! -f "$gitignore_path" ]; then
        touch "$gitignore_path"
    fi

    # 添加分隔符和标题
    if ! grep -q "# Standard Git Ignore Rules" "$gitignore_path"; then
        echo -e "\n# Standard Git Ignore Rules" >> "$gitignore_path"
        echo "# Added by automated redirect script" >> "$gitignore_path"
    fi

    # 添加标准忽略规则（如果不存在）
    for rule in "${STANDARD_IGNORE_RULES[@]}"; do
        if ! grep -qxF "$rule" "$gitignore_path"; then
            echo "$rule" >> "$gitignore_path"
        fi
    done
}

# 停止追踪特定文件
untrack_files() {
    git rm -r --cached --ignore-unmatch .idea/ .vscode/ __pycache__/ logs/ > /dev/null 2>&1
    git rm -r --cached --ignore-unmatch *.pyc *.pyo *.pyd > /dev/null 2>&1
    git rm -r --cached --ignore-unmatch .env .env.local .secret > /dev/null 2>&1
    git rm -r --cached --ignore-unmatch .DS_Store Thumbs.db > /dev/null 2>&1
}

# 处理单个仓库
process_repo() {
    local repo_dir="$1"
    echo "📦 处理仓库: $repo_dir"

    # 进入仓库目录
    cd "$repo_dir" || { echo "❌ 无法进入目录: $repo_dir"; return 1; }

    # 检测项目名称（使用目录名）
    local project_name=$(basename "$PWD")

    # 生成新的仓库URL - 修改为指定的仓库名称
    local repo_url="https://${NEW_DOMAIN}/${ORG_NAME}/new_finance_ai"

    echo "🔗 新仓库地址: $repo_url"

    # 检查是否Git仓库
    if [ ! -d ".git" ]; then
        echo "🆕 初始化 Git 仓库"
        git init
    fi

    # 添加新的远程仓库
    git remote remove origin > /dev/null 2>&1
    git remote add origin "$repo_url"

    # 配置用户信息
    git config user.name "$ORG_NAME"
    git config user.email "${ORG_NAME}@users.noreply.${NEW_DOMAIN}"  # 使用匿名邮箱

    # 更新 .gitignore 文件
    echo "🛡️  更新 .gitignore"
    update_gitignore "$PWD"

    # 停止追踪不需要的文件
    echo "🗑️  停止追踪不需要的文件"
    untrack_files

    # 添加所有更改
    git add --all

    # 提交更改
    echo "💾 提交更改"
    git commit -m "仓库迁移: 更新忽略规则，清理不需要跟踪的文件" --allow-empty

    # 创建并推送
    echo "🚀 推送到新仓库"

    # 检查并创建默认分支
    if ! git show-ref --quiet refs/heads/main; then
        git branch -M main > /dev/null 2>&1
    fi

    # 尝试推送，如果失败则提示手动创建仓库
    if ! git push -u origin main --force 2>&1; then
        echo "⚠️ 推送失败! 可能仓库尚未在 ${NEW_DOMAIN} 创建"
        echo "请手动创建仓库: $repo_url"
        echo "创建后再次运行此脚本"
        return 1
    fi

    # 返回到原始目录
    cd - > /dev/null || return

    echo -e "✅ 完成处理: $project_name\n"
}

# 查找所有项目目录
find_projects() {
    local base_dir="${1:-$PWD}"  # 使用当前目录如果未指定
    echo "🔍 在目录中搜索项目: $base_dir"

    # 查找所有包含.git目录的子目录
    find "$base_dir" -maxdepth 2 -type d -name '.git' -printf '%h\n' | while read -r dir; do
        # 跳过某些路径
        if [[ ! "$dir" =~ \/vendor\/ ]] && [[ ! "$dir" =~ \/node_modules\/ ]]; then
            echo "🏷️ 发现项目: $dir"
            process_repo "$dir"
        fi
    done

    # 查找没有.git但有项目结构的目录
    find "$base_dir" -maxdepth 1 -type d ! -name '.*' ! -name '__*' | while read -r dir; do
        if [ -d "$dir" ] && [ ! -d "$dir/.git" ]; then
            # 检查是否包含项目文件
            if find "$dir" -maxdepth 1 -type f \( -name '*.py' -o -name '*.js' -o -name '*.java' \) | read; then
                echo "🚩 候选项目: $dir (无.git)"
                read -p "是否处理此目录? [y/N] " choice
                if [[ "$choice" =~ ^[Yy]$ ]]; then
                    process_repo "$dir"
                fi
            fi
        fi
    done
}

# 主函数
main() {
    echo "🚩 开始仓库重定向与清理"
    echo "========================================"
    echo "⚙️ 配置:"
    echo " - 组织名: $ORG_NAME"
    echo " - 域名: $NEW_DOMAIN"
    echo "========================================"

    # 处理每个仓库
    if [ $# -gt 0 ]; then
        for project in "$@"; do
            if [ -d "$project" ]; then
                process_repo "$project"
            else
                echo "❌ 目录不存在: $project"
            fi
        done
    else
        find_projects "."
    fi

    echo "========================================"
    echo "🎉 所有仓库处理完成！"
}

# 执行主函数
main "$@"