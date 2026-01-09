"""
线程工具模块

提供异步/同步转换工具，用于处理 boto3 等同步 SDK。
"""

import asyncio
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from typing import TypeVar

# 全局线程池，用于执行同步阻塞操作
_executor: ThreadPoolExecutor | None = None

T = TypeVar("T")


def get_executor() -> ThreadPoolExecutor:
    """
    获取全局线程池

    Returns:
        ThreadPoolExecutor: 全局线程池实例
    """
    global _executor
    if _executor is None:
        _executor = ThreadPoolExecutor(max_workers=10, thread_name_prefix="cloudmonitor-")
    return _executor


async def run_blocking[T](func: Callable[..., T], *args: object, **kwargs: object) -> T:
    """
    在线程池中运行同步阻塞函数

    用于包装 boto3 等同步 SDK 调用，避免阻塞事件循环。

    Args:
        func: 要执行的同步函数
        *args: 位置参数
        **kwargs: 关键字参数

    Returns:
        函数返回值

    Example:
        # 包装 boto3 调用
        result = await run_blocking(client.describe_instances)

        # 带参数的调用
        result = await run_blocking(client.get_object, Bucket='my-bucket', Key='my-key')
    """
    loop = asyncio.get_running_loop()
    executor = get_executor()

    # 使用 functools.partial 绑定参数
    if kwargs:
        import functools

        func = functools.partial(func, **kwargs)

    return await loop.run_in_executor(executor, func, *args)


def shutdown_executor() -> None:
    """
    关闭全局线程池

    应在应用退出时调用以释放资源。
    """
    global _executor
    if _executor is not None:
        _executor.shutdown(wait=False)
        _executor = None
