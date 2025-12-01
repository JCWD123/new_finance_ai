#!/usr/bin/env python3
"""
金融学长AI - 图形化聊天界面

基于Tkinter的现代化聊天GUI应用
"""

import os
import sys
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import threading
import asyncio
from datetime import datetime
import queue
import webbrowser

# 添加项目路径
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

class ChatGUI:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("金融学长 AI 聊天助手")
        self.root.geometry("900x700")
        self.root.configure(bg="#f0f0f0")
        
        # 设置窗口图标（如果有的话）
        try:
            self.root.iconbitmap("icon.ico")
        except:
            pass
        
        # 聊天服务相关
        self.chat_service = None
        self.conversation_id = None
        self.user_id = "gui_user"
        
        # 线程和队列
        self.message_queue = queue.Queue()
        self.is_thinking = False
        
        # 初始化UI
        self.setup_ui()
        self.setup_chat_service()
        
        # 启动消息处理循环
        self.process_messages()
    
    def setup_ui(self):
        """设置用户界面"""
        # 主框架
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # 配置网格权重
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(1, weight=1)
        
        # 标题栏
        self.create_header(main_frame)
        
        # 聊天显示区域
        self.create_chat_area(main_frame)
        
        # 输入区域
        self.create_input_area(main_frame)
        
        # 状态栏
        self.create_status_bar(main_frame)
        
        # 侧边栏（功能按钮）
        self.create_sidebar(main_frame)
    
    def create_header(self, parent):
        """创建标题栏"""
        header_frame = ttk.Frame(parent)
        header_frame.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        header_frame.columnconfigure(1, weight=1)
        
        # 标题
        title_label = ttk.Label(
            header_frame, 
            text="🤖 金融学长 AI 聊天助手", 
            font=("Arial", 16, "bold")
        )
        title_label.grid(row=0, column=0, sticky=tk.W)
        
        # 状态指示器
        self.status_label = ttk.Label(
            header_frame, 
            text="🔄 正在初始化...", 
            font=("Arial", 10),
            foreground="orange"
        )
        self.status_label.grid(row=0, column=1, sticky=tk.E)
        
        # 分隔线
        separator = ttk.Separator(header_frame, orient='horizontal')
        separator.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(5, 0))
    
    def create_chat_area(self, parent):
        """创建聊天显示区域"""
        chat_frame = ttk.Frame(parent)
        chat_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=(0, 10))
        chat_frame.columnconfigure(0, weight=1)
        chat_frame.rowconfigure(0, weight=1)
        
        # 聊天文本框
        self.chat_text = scrolledtext.ScrolledText(
            chat_frame,
            wrap=tk.WORD,
            width=60,
            height=25,
            font=("Arial", 11),
            bg="white",
            fg="black",
            insertbackground="blue",
            selectbackground="lightblue"
        )
        self.chat_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # 配置文本标签样式
        self.chat_text.tag_configure("user", foreground="blue", font=("Arial", 11, "bold"))
        self.chat_text.tag_configure("ai", foreground="green", font=("Arial", 11, "bold"))
        self.chat_text.tag_configure("system", foreground="gray", font=("Arial", 10, "italic"))
        self.chat_text.tag_configure("error", foreground="red", font=("Arial", 11))
        self.chat_text.tag_configure("thinking", foreground="orange", font=("Arial", 10, "italic"))
        
        # 禁用编辑
        self.chat_text.configure(state='disabled')
        
        # 欢迎消息
        self.add_system_message("欢迎使用金融学长AI聊天助手！")
        self.add_system_message("我可以帮您分析股市行情、解答金融问题。")
        self.add_system_message("请在下方输入您的问题...")
    
    def create_input_area(self, parent):
        """创建输入区域"""
        input_frame = ttk.Frame(parent)
        input_frame.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=(10, 0), padx=(0, 10))
        input_frame.columnconfigure(0, weight=1)
        
        # 输入框
        self.input_var = tk.StringVar()
        self.input_entry = ttk.Entry(
            input_frame,
            textvariable=self.input_var,
            font=("Arial", 12),
            width=50
        )
        self.input_entry.grid(row=0, column=0, sticky=(tk.W, tk.E), padx=(0, 10))
        
        # 发送按钮
        self.send_button = ttk.Button(
            input_frame,
            text="发送",
            command=self.send_message,
            width=10
        )
        self.send_button.grid(row=0, column=1)
        
        # 绑定回车键
        self.input_entry.bind('<Return>', lambda e: self.send_message())
        
        # 快捷操作按钮
        button_frame = ttk.Frame(input_frame)
        button_frame.grid(row=1, column=0, columnspan=2, pady=(5, 0))
        
        ttk.Button(button_frame, text="清空对话", command=self.clear_chat, width=12).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(button_frame, text="示例问题", command=self.show_examples, width=12).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(button_frame, text="导出对话", command=self.export_chat, width=12).pack(side=tk.LEFT)
    
    def create_sidebar(self, parent):
        """创建侧边栏"""
        sidebar_frame = ttk.LabelFrame(parent, text="功能面板", padding="10")
        sidebar_frame.grid(row=1, column=1, rowspan=2, sticky=(tk.N, tk.S, tk.E), padx=(10, 0))
        
        # 数据库状态
        ttk.Label(sidebar_frame, text="数据库状态:", font=("Arial", 10, "bold")).pack(anchor=tk.W, pady=(0, 5))
        self.db_status_label = ttk.Label(sidebar_frame, text="🔄 检查中...", font=("Arial", 9))
        self.db_status_label.pack(anchor=tk.W, pady=(0, 10))
        
        # 对话统计
        ttk.Label(sidebar_frame, text="对话统计:", font=("Arial", 10, "bold")).pack(anchor=tk.W, pady=(0, 5))
        self.stats_label = ttk.Label(sidebar_frame, text="消息数: 0", font=("Arial", 9))
        self.stats_label.pack(anchor=tk.W, pady=(0, 10))
        
        # 快捷功能
        ttk.Label(sidebar_frame, text="快捷功能:", font=("Arial", 10, "bold")).pack(anchor=tk.W, pady=(0, 5))
        
        ttk.Button(sidebar_frame, text="股市行情分析", 
                  command=lambda: self.quick_question("请帮我分析一下今天的股市行情")).pack(fill=tk.X, pady=2)
        ttk.Button(sidebar_frame, text="美债收益率", 
                  command=lambda: self.quick_question("什么是美债收益率？它对股市有什么影响？")).pack(fill=tk.X, pady=2)
        ttk.Button(sidebar_frame, text="VIX指数", 
                  command=lambda: self.quick_question("VIX指数是什么意思？")).pack(fill=tk.X, pady=2)
        ttk.Button(sidebar_frame, text="投资建议", 
                  command=lambda: self.quick_question("请给我一些投资理财的建议")).pack(fill=tk.X, pady=2)
        
        # 分隔线
        ttk.Separator(sidebar_frame, orient='horizontal').pack(fill=tk.X, pady=10)
        
        # 帮助按钮
        ttk.Button(sidebar_frame, text="使用帮助", command=self.show_help).pack(fill=tk.X, pady=2)
        ttk.Button(sidebar_frame, text="关于软件", command=self.show_about).pack(fill=tk.X, pady=2)
    
    def create_status_bar(self, parent):
        """创建状态栏"""
        status_frame = ttk.Frame(parent)
        status_frame.grid(row=3, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(10, 0))
        status_frame.columnconfigure(1, weight=1)
        
        # 状态信息
        self.bottom_status_label = ttk.Label(status_frame, text="就绪", font=("Arial", 9))
        self.bottom_status_label.grid(row=0, column=0, sticky=tk.W)
        
        # 时间显示
        self.time_label = ttk.Label(status_frame, text="", font=("Arial", 9))
        self.time_label.grid(row=0, column=1, sticky=tk.E)
        self.update_time()
    
    def setup_chat_service(self):
        """在后台线程中初始化聊天服务"""
        def init_service():
            try:
                from services.chat_service import LocalChatService
                self.chat_service = LocalChatService()
                
                # 获取数据库统计
                stats = self.chat_service.doc_manager.vector_service.get_stats()
                doc_count = stats.get('total_documents', 0)
                
                # 更新UI
                self.message_queue.put(('status', 'ready', f"✅ 已连接 ({doc_count}个文档)"))
                self.message_queue.put(('db_status', f"📚 {doc_count} 个文档"))
                self.message_queue.put(('system', "聊天服务已就绪，您可以开始提问了！"))
                
            except Exception as e:
                self.message_queue.put(('status', 'error', "❌ 初始化失败"))
                self.message_queue.put(('error', f"初始化聊天服务失败: {str(e)}"))
        
        # 在后台线程中初始化
        threading.Thread(target=init_service, daemon=True).start()
    
    def process_messages(self):
        """处理消息队列"""
        try:
            while True:
                msg_type, *args = self.message_queue.get_nowait()
                
                if msg_type == 'status':
                    status, text = args
                    self.status_label.config(text=text)
                    if status == 'ready':
                        self.status_label.config(foreground="green")
                    elif status == 'error':
                        self.status_label.config(foreground="red")
                    else:
                        self.status_label.config(foreground="orange")
                
                elif msg_type == 'db_status':
                    self.db_status_label.config(text=args[0])
                
                elif msg_type == 'system':
                    self.add_system_message(args[0])
                
                elif msg_type == 'error':
                    self.add_error_message(args[0])
                
                elif msg_type == 'ai_response':
                    self.add_ai_message(args[0], args[1] if len(args) > 1 else False)
                    self.set_thinking(False)
                
                elif msg_type == 'thinking_done':
                    self.set_thinking(False)
        
        except queue.Empty:
            pass
        
        # 继续处理
        self.root.after(100, self.process_messages)
    
    def add_message(self, message, tag=None, timestamp=True):
        """添加消息到聊天区域"""
        self.chat_text.configure(state='normal')
        
        if timestamp:
            time_str = datetime.now().strftime("%H:%M:%S")
            self.chat_text.insert(tk.END, f"[{time_str}] ")
        
        if tag:
            self.chat_text.insert(tk.END, message + "\n", tag)
        else:
            self.chat_text.insert(tk.END, message + "\n")
        
        self.chat_text.configure(state='disabled')
        self.chat_text.see(tk.END)
    
    def add_user_message(self, message):
        """添加用户消息"""
        self.add_message(f"💬 您: {message}", "user")
    
    def add_ai_message(self, message, context_used=False):
        """添加AI消息"""
        context_info = "📚 基于历史文章" if context_used else "💭 基于一般知识"
        self.add_message(f"🤖 AI: {message}", "ai")
        self.add_message(f"    {context_info}", "system", False)
    
    def add_system_message(self, message):
        """添加系统消息"""
        self.add_message(f"ℹ️ {message}", "system")
    
    def add_error_message(self, message):
        """添加错误消息"""
        self.add_message(f"❌ {message}", "error")
    
    def set_thinking(self, thinking):
        """设置思考状态"""
        self.is_thinking = thinking
        if thinking:
            self.send_button.config(state='disabled', text="思考中...")
            self.input_entry.config(state='disabled')
            self.add_message("🤔 AI正在思考...", "thinking")
            self.bottom_status_label.config(text="AI正在思考...")
        else:
            self.send_button.config(state='normal', text="发送")
            self.input_entry.config(state='normal')
            self.bottom_status_label.config(text="就绪")
            # 移除思考消息
            self.chat_text.configure(state='normal')
            content = self.chat_text.get("1.0", tk.END)
            lines = content.split('\n')
            if lines and "🤔 AI正在思考..." in lines[-2]:
                # 删除最后的思考消息
                self.chat_text.delete("end-2l", "end-1l")
            self.chat_text.configure(state='disabled')
    
    def send_message(self):
        """发送消息"""
        if self.is_thinking:
            return
        
        message = self.input_var.get().strip()
        if not message:
            return
        
        # 清空输入框
        self.input_var.set("")
        
        # 显示用户消息
        self.add_user_message(message)
        
        # 检查聊天服务
        if not self.chat_service:
            self.add_error_message("聊天服务未就绪，请稍候重试")
            return
        
        # 设置思考状态
        self.set_thinking(True)
        
        # 在后台线程中处理
        def process_message():
            try:
                # 创建新的事件循环
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
                # 调用聊天服务
                result = loop.run_until_complete(
                    self.chat_service.chat(
                        query=message,
                        conversation_id=self.conversation_id,
                        user_id=self.user_id
                    )
                )
                
                if "error" in result:
                    self.message_queue.put(('error', result["error"]))
                else:
                    self.conversation_id = result["conversation_id"]
                    answer = result.get("answer", "抱歉，我无法回答这个问题。")
                    context_used = result.get("context_used", False)
                    
                    self.message_queue.put(('ai_response', answer, context_used))
                    
                    # 更新统计
                    self.update_stats()
                
            except Exception as e:
                self.message_queue.put(('error', f"处理消息时出错: {str(e)}"))
            finally:
                self.message_queue.put(('thinking_done',))
        
        # 启动后台线程
        threading.Thread(target=process_message, daemon=True).start()
    
    def quick_question(self, question):
        """快速提问"""
        self.input_var.set(question)
        self.send_message()
    
    def clear_chat(self):
        """清空对话"""
        if messagebox.askyesno("确认", "确定要清空对话记录吗？"):
            self.chat_text.configure(state='normal')
            self.chat_text.delete(1.0, tk.END)
            self.chat_text.configure(state='disabled')
            self.add_system_message("对话已清空")
            self.conversation_id = None
    
    def show_examples(self):
        """显示示例问题"""
        examples = [
            "请帮我分析一下今天的股市行情",
            "什么是美债收益率？它对股市有什么影响？",
            "VIX指数是什么意思？",
            "请给我一些投资理财的建议",
            "如何分析一只股票的基本面？",
            "什么是技术分析？常用指标有哪些？"
        ]
        
        example_window = tk.Toplevel(self.root)
        example_window.title("示例问题")
        example_window.geometry("400x300")
        example_window.transient(self.root)
        example_window.grab_set()
        
        ttk.Label(example_window, text="点击问题快速提问:", font=("Arial", 12, "bold")).pack(pady=10)
        
        for example in examples:
            btn = ttk.Button(
                example_window, 
                text=example,
                command=lambda q=example: [example_window.destroy(), self.quick_question(q)]
            )
            btn.pack(fill=tk.X, padx=20, pady=2)
    
    def export_chat(self):
        """导出对话"""
        try:
            from tkinter import filedialog
            filename = filedialog.asksaveasfilename(
                defaultextension=".txt",
                filetypes=[("文本文件", "*.txt"), ("所有文件", "*.*")]
            )
            if filename:
                content = self.chat_text.get(1.0, tk.END)
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(f"金融学长AI聊天记录\n")
                    f.write(f"导出时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                    f.write("=" * 50 + "\n\n")
                    f.write(content)
                messagebox.showinfo("成功", "对话记录已导出")
        except Exception as e:
            messagebox.showerror("错误", f"导出失败: {str(e)}")
    
    def show_help(self):
        """显示帮助"""
        help_text = """
金融学长AI聊天助手使用帮助

🎯 主要功能：
• 股市行情分析
• 金融知识问答  
• 投资建议咨询
• 技术指标解释

💡 使用技巧：
• 问题尽量具体明确
• 可以询问实时市场分析
• 支持多轮对话
• 右侧有快捷问题按钮

⚠️ 注意事项：
• 所有建议仅供参考
• 投资有风险，决策需谨慎
• 不构成具体投资建议

🔧 快捷键：
• Enter - 发送消息
• Ctrl+L - 清空对话
        """
        
        help_window = tk.Toplevel(self.root)
        help_window.title("使用帮助")
        help_window.geometry("500x400")
        help_window.transient(self.root)
        
        text_widget = scrolledtext.ScrolledText(help_window, wrap=tk.WORD, font=("Arial", 10))
        text_widget.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        text_widget.insert(1.0, help_text)
        text_widget.configure(state='disabled')
    
    def show_about(self):
        """显示关于"""
        about_text = """
金融学长AI聊天助手 v1.0

🤖 基于大语言模型的智能金融助手
📚 集成历史文章数据库进行RAG检索
🎯 专注于金融市场分析和投资咨询

技术栈：
• Python + Tkinter (GUI)
• FAISS (向量数据库)
• GLM-4-Flash (大语言模型)
• MongoDB (数据存储)

开发团队：金融学长项目组
版本：1.0.0
更新时间：2025年6月

⚠️ 免责声明：
本软件提供的所有信息和建议仅供参考，
不构成投资建议。投资有风险，决策需谨慎。
        """
        
        messagebox.showinfo("关于软件", about_text)
    
    def update_stats(self):
        """更新统计信息"""
        # 这里可以添加更详细的统计逻辑
        content = self.chat_text.get(1.0, tk.END)
        message_count = content.count("💬 您:") + content.count("🤖 AI:")
        self.stats_label.config(text=f"消息数: {message_count}")
    
    def update_time(self):
        """更新时间显示"""
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.time_label.config(text=current_time)
        self.root.after(1000, self.update_time)
    
    def on_closing(self):
        """关闭窗口时的处理"""
        if messagebox.askokcancel("退出", "确定要退出聊天助手吗？"):
            self.root.destroy()
    
    def run(self):
        """运行GUI应用"""
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        # 绑定快捷键
        self.root.bind('<Control-l>', lambda e: self.clear_chat())
        
        # 启动应用
        self.root.mainloop()

def main():
    """主函数"""
    try:
        app = ChatGUI()
        app.run()
    except Exception as e:
        print(f"启动GUI失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main() 