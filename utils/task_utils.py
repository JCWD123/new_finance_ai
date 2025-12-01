import asyncio
import concurrent.futures
import inspect
import multiprocessing
import pickle
from typing import List, Callable, Any, Dict

from config.settings import PROCESS_POOL
from logger import task_logger


class TaskManager:
    """
    任务管理器 - 混合多进程/多线程和协程
    - 优先使用多进程分配计算任务
    - 如果不能使用多进程，则使用多线程
    - 子进程/线程内使用协程处理I/O
    """

    def __init__(self):
        """
        初始化任务管理器

        Args:
            default_process_workers: 默认进程池大小，None表示使用CPU核心数
            default_thread_workers: 默认线程池大小，None表示使用CPU核心数*2
        """
        self.default_process_workers = PROCESS_POOL["process_workers"] or max(
            1, multiprocessing.cpu_count() - 1
        )
        self.default_thread_workers = PROCESS_POOL["thread_workers"] or max(
            1, multiprocessing.cpu_count() * 2
        )

    def _is_serializable(self, obj: Any) -> bool:
        """检查对象是否可序列化(适合多进程通信)"""
        try:
            pickle.dumps(obj)
            return True
        except:
            return False

    def _can_use_multiprocessing(
        self, func: Callable, items: List, kwargs: Dict
    ) -> bool:
        """判断任务是否适合多进程处理"""
        # 检查函数是否可序列化
        if hasattr(func, "__self__") and not isinstance(
            func.__self__, type
        ):  # 绑定方法
            # 有些类实例方法可能依赖实例状态，无法跨进程传递
            return False

        # 检查函数所在模块是否是__main__
        if func.__module__ == "__main__":
            return False

        # 抽样检查数据是否可序列化
        sample_items = items[: min(2, len(items))]
        if items and len(items) > 2:
            sample_items.append(items[-1])

        for item in sample_items:
            if not self._is_serializable(item):
                return False

        # 检查关键字参数
        for k, v in kwargs.items():
            if not self._is_serializable(v):
                return False

        return True

    async def _run_async_in_process(
        self, async_func: Callable, chunk: List, **kwargs
    ) -> List:
        """在进程内使用协程处理一组任务"""
        if not chunk:
            return []

        # 创建任务
        tasks = [async_func(item, **kwargs) for item in chunk]

        # 收集结果
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 过滤掉异常
        valid_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                task_logger.error(f"任务处理失败: {str(result)}")
            else:
                valid_results.append(result)

        return valid_results

    def _process_worker(
        self, async_func_name: str, async_func_module: str, chunk: List, kwargs: Dict
    ) -> List:
        """进程工作函数 - 在进程内运行协程批次"""
        try:
            # 动态导入函数
            import importlib

            module = importlib.import_module(async_func_module)
            async_func = getattr(module, async_func_name)

            # 设置新的事件循环
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            try:
                # 运行协程批次
                return loop.run_until_complete(
                    self._run_async_in_process(async_func, chunk, **kwargs)
                )
            finally:
                loop.close()
        except Exception as e:
            task_logger.error(f"进程工作函数执行失败: {str(e)}", exc_info=True)
            return []

    async def _run_in_thread_pool(
        self, async_func: Callable, items: List, thread_count: int, **kwargs
    ) -> List:
        """在线程池中运行协程任务"""
        if not items:
            return []

        task_logger.info(f"使用多线程模式，线程数: {thread_count}")

        # 分块处理
        chunk_size = max(1, len(items) // thread_count)
        chunks = [items[i : i + chunk_size] for i in range(0, len(items), chunk_size)]

        all_results = []

        # 线程工作函数
        def thread_worker(chunk):
            # 创建新的事件循环给线程使用
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                # 运行协程批次
                tasks = [async_func(item, **kwargs) for item in chunk]
                results = loop.run_until_complete(
                    asyncio.gather(*tasks, return_exceptions=True)
                )

                # 过滤掉异常
                valid_results = []
                for result in results:
                    if isinstance(result, Exception):
                        task_logger.error(
                            f"线程任务处理失败: {str(result)}", exc_info=True
                        )
                    else:
                        valid_results.append(result)

                return valid_results
            finally:
                loop.close()

        # 使用线程池
        with concurrent.futures.ThreadPoolExecutor(
            max_workers=thread_count
        ) as executor:
            futures = [executor.submit(thread_worker, chunk) for chunk in chunks]

            # 收集结果
            for future in concurrent.futures.as_completed(futures):
                try:
                    result = future.result()
                    all_results.extend(result)
                except Exception as e:
                    task_logger.error(f"线程任务执行失败: {str(e)}", exc_info=True)

        return all_results

    async def process_tasks(
        self,
        async_func: Callable,
        items: List,
        use_processes: bool = True,
        use_threads: bool = True,
        process_count: int = None,
        thread_count: int = None,
        **kwargs,
    ) -> List:
        """
        处理任务 - 多进程/多线程分配，协程处理

        Args:
            async_func: 异步处理函数
            items: 需要处理的项目列表
            use_processes: 是否使用多进程，默认为True
            use_threads: 是否在多进程不可用时使用多线程，默认为True
            process_count: 进程数，默认为系统CPU核心数-1
            thread_count: 线程数，默认为系统CPU核心数*2
            **kwargs: 传递给处理函数的额外参数

        Returns:
            处理结果列表
        """
        if not items:
            return []

        # 检查是否是异步函数
        if not inspect.iscoroutinefunction(async_func):
            raise ValueError("只支持异步函数处理")

        # 如果不使用多进程和多线程，则直接在当前进程使用协程
        if not use_processes and not use_threads:
            task_logger.info("按用户设置，在当前进程使用协程处理任务")
            return await self._run_async_in_process(async_func, items, **kwargs)

        # 确定是否可以使用多进程
        can_use_mp = use_processes and self._can_use_multiprocessing(
            async_func, items, kwargs
        )

        # 如果可以使用多进程
        if can_use_mp:
            # 确定进程数和块大小
            process_count = min(
                process_count or self.default_process_workers, len(items)
            )
            if process_count <= 1:
                # 单进程情况可以考虑多线程
                pass
            else:
                # 获取函数信息，用于在子进程中重新加载
                func_name = async_func.__name__
                func_module = async_func.__module__

                task_logger.info(f"使用多进程模式，进程数: {process_count}")

                # 创建进程池执行任务
                all_results = []
                with concurrent.futures.ProcessPoolExecutor(
                    max_workers=process_count
                ) as executor:
                    # 提交所有任务
                    futures = [
                        executor.submit(
                            self._process_worker, func_name, func_module, chunk, kwargs
                        )
                        for chunk in items
                    ]

                    # 收集结果
                    for future in concurrent.futures.as_completed(futures):
                        try:
                            result = future.result()
                            all_results.extend(result)
                        except Exception as e:
                            task_logger.error(
                                f"进程任务执行失败: {str(e)}", exc_info=True
                            )

                return all_results

        # 如果不能使用多进程，但可以使用多线程
        if use_threads:
            thread_count = thread_count or self.default_thread_workers
            if thread_count > 1:
                return await self._run_in_thread_pool(
                    async_func, items, thread_count, **kwargs
                )

        # 如果都不能使用，就在当前进程使用协程
        task_logger.warning("无法使用多进程或多线程，将在当前进程使用协程")
        return await self._run_async_in_process(async_func, items, **kwargs)

    async def process_in_current_process(
        self, async_func: Callable, items: List, **kwargs
    ) -> List:
        """
        在当前进程中使用协程处理任务
        适用于不适合多进程的场景

        Args:
            async_func: 异步处理函数
            items: 需要处理的项目列表
            **kwargs: 传递给处理函数的额外参数
        """
        return await self._run_async_in_process(async_func, items, **kwargs)

    async def batch_process(
        self,
        async_func: Callable,
        items: List,
        batch_size: int = 10,
        use_processes: bool = True,
        process_count: int = None,
        **kwargs,
    ) -> List:
        """
        批量处理任务，适用于大量任务需要分批处理的场景

        Args:
            async_func: 异步处理函数
            items: 需要处理的项目列表
            batch_size: 每批处理的项目数量
            use_processes: 是否使用多进程，默认为True
            process_count: 进程数
            **kwargs: 传递给处理函数的额外参数
        """
        if not items:
            return []

        # 分批处理
        all_results = []
        for i in range(0, len(items), batch_size):
            batch = items[i : i + batch_size]
            results = await self.process_tasks(
                async_func,
                batch,
                use_processes=use_processes,
                process_count=process_count,
                **kwargs,
            )
            all_results.extend(results)

        return all_results
