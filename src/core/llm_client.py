"""教员AI顾问 - Ollama异步LLM客户端

基于aiohttp的异步Ollama API客户端，支持：
- 异步HTTP调用（连接池复用）
- Qwen3 Thinking模式（
  
  标签解析）
- SSE流式输出
- 自动重试（3次，指数退避）
- 完整的错误处理和日志记录

作者: AI系统架构师
版本: 3.0.0
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any, AsyncGenerator, Dict, List, Optional, Union

import aiohttp
from aiohttp import ClientTimeout, TCPConnector

logger = logging.getLogger(__name__)


# ============================================================================
# 常量定义
# ============================================================================

DEFAULT_OLLAMA_HOST = "http://localhost:11434"
DEFAULT_MODEL = "qwen3:8b"
DEFAULT_TIMEOUT = 120  # 秒（增加到120秒，避免模型加载超时）
MAX_RETRIES = 3
RETRY_BASE_DELAY = 1.0  # 基础退避时间（秒）

# Thinking标签解析
THINK_START_TAG = "
  "
THINK_END_TAG = "
  "


class OllamaError(Exception):
    """Ollama API调用异常"""
    pass


class OllamaTimeoutError(OllamaError):
    """Ollama API超时异常"""
    pass


class OllamaResponseError(OllamaError):
    """Ollama API响应错误"""
    def __init__(self, message: str, status_code: int = 0, response_body: str = ""):
        super().__init__(message)
        self.status_code = status_code
        self.response_body = response_body


# ============================================================================
# Ollama异步客户端
# ============================================================================

class OllamaClient:
    """
    异步Ollama API客户端

    特性：
    - 使用aiohttp连接池，支持HTTP/1.1 keep-alive
    - 自动重试3次，指数退避（1s, 2s, 4s）
    - 支持Qwen3 Thinking模式（解析
  标签）
    - 支持SSE流式输出
    - 完整的类型注解和日志记录

    用法：
        client = OllamaClient()
        response = await client.chat([{"role": "user", "content": "..."}])
        thinking = response.get("thinking", "")
        content = response["message"]["content"]

        # 流式调用
        async for chunk in client.chat_stream(messages):
            print(chunk.get("content", ""), end="", flush=True)
    """

    def __init__(
        self,
        base_url: str = DEFAULT_OLLAMA_HOST,
        model: str = DEFAULT_MODEL,
        timeout: int = DEFAULT_TIMEOUT,
        max_retries: int = MAX_RETRIES,
        connection_pool_size: int = 10,
    ):
        """
        初始化Ollama客户端

        Args:
            base_url: Ollama服务地址，默认 http://localhost:11434
            model: 默认模型名，默认 qwen3:8b
            timeout: 请求超时（秒），默认60
            max_retries: 最大重试次数，默认3
            connection_pool_size: 连接池大小，默认10
        """
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self.max_retries = max_retries
        self.connection_pool_size = connection_pool_size

        # API端点
        self.chat_endpoint = f"{self.base_url}/api/chat"
        self.generate_endpoint = f"{self.base_url}/api/generate"

        # aiohttp会话（懒加载）
        self._session: Optional[aiohttp.ClientSession] = None
        self._connector: Optional[TCPConnector] = None
        self._closed: bool = True

        logger.info(
            "OllamaClient initialized: base_url=%s, model=%s, timeout=%ds, "
            "max_retries=%d, pool_size=%d",
            self.base_url, self.model, self.timeout, self.max_retries,
            self.connection_pool_size,
        )

    async def _ensure_session(self) -> aiohttp.ClientSession:
        """
        确保aiohttp会话已创建（连接池复用）

        Returns:
            aiohttp.ClientSession实例
        """
        if self._session is None or self._session.closed:
            self._connector = TCPConnector(
                limit=self.connection_pool_size,
                limit_per_host=self.connection_pool_size,
                ttl_dns_cache=300,
                use_dns_cache=True,
                enable_cleanup_closed=True,
                force_close=False,
            )
            timeout = ClientTimeout(total=self.timeout, connect=10)
            self._session = aiohttp.ClientSession(
                connector=self._connector,
                timeout=timeout,
                headers={"Content-Type": "application/json"},
            )
            self._closed = False
            logger.debug("Created new aiohttp session with pool size %d", self.connection_pool_size)
        return self._session

    async def close(self) -> None:
        """关闭客户端，释放连接池资源"""
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None
        if self._connector and not self._connector.closed:
            await self._connector.close()
            self._connector = None
        self._closed = True
        logger.info("OllamaClient closed")

    async def __aenter__(self) -> OllamaClient:
        """异步上下文管理器入口"""
        await self._ensure_session()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """异步上下文管理器出口"""
        await self.close()

    def _parse_thinking_content(self, content: str) -> tuple[str, str]:
        """
        解析Qwen3的
  标签内容

        Qwen3在Thinking模式下会输出：
             
  内部思考过程...
  最终回复内容

        Args:
            content: 原始响应内容

        Returns:
            (thinking_content, response_content) 元组
        """
        thinking = ""
        response = content

        start_idx = content.find(THINK_START_TAG)
        end_idx = content.find(THINK_END_TAG)

        if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
            thinking_start = start_idx + len(THINK_START_TAG)
            thinking = content[thinking_start:end_idx].strip()
            # 移除think标签，只保留实际响应
            response = (content[:start_idx] + content[end_idx + len(THINK_END_TAG):]).strip()
            logger.debug("Parsed thinking content: %d chars", len(thinking))

        return thinking, response

    def _build_request_body(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        options: Optional[Dict[str, Any]] = None,
        thinking: bool = True,
        stream: bool = False,
    ) -> Dict[str, Any]:
        """
        构建请求体

        Args:
            messages: 消息列表
            model: 模型名（覆盖默认）
            options: 额外选项（temperature等）
            thinking: 是否启用Thinking模式
            stream: 是否流式输出

        Returns:
            请求体字典
        """
        body: Dict[str, Any] = {
            "model": model or self.model,
            "messages": messages,
            "stream": stream,
        }

        # 合并选项
        opts = {}
        if options:
            opts.update(options)

        # Thinking模式：Qwen3通过特殊token控制
        # 在options中传递enable_thinking（如果后端支持）
        if thinking:
            opts["enable_thinking"] = True
            # 确保temperature适合thinking模式
            if "temperature" not in opts:
                opts["temperature"] = 0.7
            if "top_p" not in opts:
                opts["top_p"] = 0.95
            if "top_k" not in opts:
                opts["top_k"] = 20
        else:
            opts["enable_thinking"] = False

        body["options"] = opts
        return body

    async def _do_request(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        options: Optional[Dict[str, Any]] = None,
        thinking: bool = True,
    ) -> Dict[str, Any]:
        """
        执行单次HTTP请求（内部方法）

        Args:
            messages: 消息列表
            model: 模型名
            options: 额外选项
            thinking: 是否启用Thinking模式

        Returns:
            API响应字典

        Raises:
            OllamaTimeoutError: 请求超时
            OllamaResponseError: 响应错误
        """
        session = await self._ensure_session()
        body = self._build_request_body(messages, model, options, thinking, stream=False)

        logger.debug(
            "Request to %s: model=%s, messages=%d, thinking=%s",
            self.chat_endpoint, body["model"], len(messages), thinking,
        )

        try:
            async with session.post(self.chat_endpoint, json=body) as response:
                response.raise_for_status()
                data = await response.json()

                # 解析Thinking内容
                content = data.get("message", {}).get("content", "")
                thinking_content, clean_content = self._parse_thinking_content(content)

                if thinking_content:
                    data["thinking"] = thinking_content
                    data["message"]["content"] = clean_content

                logger.debug(
                    "Response: content_len=%d, thinking_len=%d",
                    len(clean_content), len(thinking_content),
                )
                return data

        except asyncio.TimeoutError:
            raise OllamaTimeoutError(
                f"Request to Ollama timed out after {self.timeout}s"
            )
        except aiohttp.ClientResponseError as e:
            raise OllamaResponseError(
                f"Ollama API error: {e.status} {e.message}",
                status_code=e.status,
            )
        except aiohttp.ClientError as e:
            raise OllamaError(f"Ollama connection error: {e}")

    async def chat(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        options: Optional[Dict[str, Any]] = None,
        thinking: bool = True,
    ) -> Dict[str, Any]:
        """
        调用Ollama chat API（带自动重试）

        自动重试机制：
        - 最大重试3次
        - 指数退避：1s, 2s, 4s
        - 只对可重试错误重试（超时、连接错误）
        - 4xx错误不重试

        Args:
            messages: 消息列表，格式 [{"role": "user", "content": "..."}, ...]
            model: 模型名，默认使用初始化时指定的模型
            options: LLM选项，如 {"temperature": 0.7, "num_ctx": 8192}
            thinking: 是否启用Qwen3 Thinking模式，默认True

        Returns:
            API响应字典，包含：
            {
                "message": {"role": "assistant", "content": "..."},
                "thinking": "内部思考过程...",  # 仅启用thinking时存在
                "done": true,
                "total_duration": ...,
                ...
            }

        Raises:
            OllamaError: 所有重试均失败时抛出

        Example:
            client = OllamaClient()
            response = await client.chat([
                {"role": "system", "content": "你是教员..."},
                {"role": "user", "content": "我想创业..."},
            ])
            print(response["message"]["content"])
            if "thinking" in response:
                print("Thinking:", response["thinking"])
        """
        last_error: Optional[Exception] = None

        for attempt in range(1, self.max_retries + 1):
            try:
                start_time = time.time()
                result = await self._do_request(messages, model, options, thinking)
                elapsed = int((time.time() - start_time) * 1000)
                logger.info(
                    "Chat completed in %dms (attempt %d/%d)",
                    elapsed, attempt, self.max_retries,
                )
                return result

            except OllamaResponseError as e:
                # 4xx错误不重试
                if 400 <= e.status_code < 500:
                    logger.error(
                        "Client error %d, not retrying: %s",
                        e.status_code, e,
                    )
                    raise
                logger.warning(
                    "Attempt %d/%d failed with status %d: %s",
                    attempt, self.max_retries, e.status_code, e,
                )
                last_error = e

            except OllamaTimeoutError as e:
                logger.warning(
                    "Attempt %d/%d timed out: %s",
                    attempt, self.max_retries, e,
                )
                last_error = e

            except OllamaError as e:
                logger.warning(
                    "Attempt %d/%d failed: %s",
                    attempt, self.max_retries, e,
                )
                last_error = e

            # 等待后退避（最后一次不等待）
            if attempt < self.max_retries:
                delay = RETRY_BASE_DELAY * (2 ** (attempt - 1))
                logger.info("Retrying in %.1fs (attempt %d/%d)...", delay, attempt + 1, self.max_retries)
                await asyncio.sleep(delay)

        # 所有重试均失败
        raise OllamaError(
            f"All {self.max_retries} attempts failed. Last error: {last_error}"
        ) from last_error

    async def chat_stream(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        options: Optional[Dict[str, Any]] = None,
        thinking: bool = True,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        流式调用Ollama chat API（SSE格式）

        用于前端实时显示，逐字返回内容。
        -thinking内容会单独以 chunk_type="thinking" 的形式返回。

        Args:
            messages: 消息列表
            model: 模型名
            options: LLM选项
            thinking: 是否启用Thinking模式

        Yields:
            内容块字典：
            - {"type": "thinking", "content": "..."}  # thinking内容
            - {"type": "content", "content": "..."}    # 响应内容
            - {"type": "done", "content": ""}          # 完成标记

        Example:
            async for chunk in client.chat_stream(messages):
                if chunk["type"] == "thinking":
                    print(f"[Thinking] {chunk['content']}")
                elif chunk["type"] == "content":
                    print(chunk["content"], end="", flush=True)
                elif chunk["type"] == "done":
                    print("\\n[Done]")
        """
        session = await self._ensure_session()
        body = self._build_request_body(messages, model, options, thinking, stream=True)

        logger.debug(
            "Stream request: model=%s, messages=%d", body["model"], len(messages),
        )

        thinking_buffer = ""
        in_thinking = False
        start_time = time.time()

        try:
            async with session.post(self.chat_endpoint, json=body) as response:
                response.raise_for_status()

                async for line in response.content:
                    line = line.decode("utf-8").strip()
                    if not line:
                        continue

                    try:
                        data = json.loads(line)
                    except json.JSONDecodeError:
                        continue

                    content = data.get("message", {}).get("content", "")
                    if not content:
                        if data.get("done", False):
                            yield {"type": "done", "content": ""}
                        continue

                    # 解析thinking标签（流式模式）
                    if thinking:
                        if THINK_START_TAG in content and not in_thinking:
                            in_thinking = True
                            # 提取think标签前的内容
                            before = content[:content.find(THINK_START_TAG)]
                            if before:
                                yield {"type": "content", "content": before}
                            continue

                        if in_thinking:
                            if THINK_END_TAG in content:
                                in_thinking = False
                                after = content[content.find(THINK_END_TAG) + len(THINK_END_TAG):]
                                if after:
                                    yield {"type": "content", "content": after}
                            else:
                                thinking_buffer += content
                                yield {"type": "thinking", "content": content}
                            continue

                    yield {"type": "content", "content": content}

                    if data.get("done", False):
                        elapsed = int((time.time() - start_time) * 1000)
                        logger.info("Stream completed in %dms", elapsed)
                        yield {"type": "done", "content": ""}

        except asyncio.TimeoutError:
            raise OllamaTimeoutError(f"Stream request timed out after {self.timeout}s")
        except aiohttp.ClientError as e:
            raise OllamaError(f"Stream connection error: {e}")

    async def generate(
        self,
        prompt: str,
        model: Optional[str] = None,
        options: Optional[Dict[str, Any]] = None,
        thinking: bool = True,
    ) -> Dict[str, Any]:
        """
        调用Ollama generate API（简化接口，直接传prompt字符串）

        Args:
            prompt: 提示文本
            model: 模型名
            options: LLM选项
            thinking: 是否启用Thinking模式

        Returns:
            API响应字典
        """
        session = await self._ensure_session()
        body = {
            "model": model or self.model,
            "prompt": prompt,
            "stream": False,
            "options": options or {},
        }

        if thinking:
            body["options"]["enable_thinking"] = True

        last_error: Optional[Exception] = None
        for attempt in range(1, self.max_retries + 1):
            try:
                async with session.post(self.generate_endpoint, json=body) as response:
                    response.raise_for_status()
                    data = await response.json()

                    # 解析Thinking内容
                    content = data.get("response", "")
                    thinking_content, clean_content = self._parse_thinking_content(content)

                    if thinking_content:
                        data["thinking"] = thinking_content
                        data["response"] = clean_content

                    return data

            except (OllamaError, aiohttp.ClientError) as e:
                last_error = e
                if attempt < self.max_retries:
                    delay = RETRY_BASE_DELAY * (2 ** (attempt - 1))
                    await asyncio.sleep(delay)

        raise OllamaError(f"Generate failed after {self.max_retries} attempts: {last_error}")

    async def health_check(self) -> bool:
        """
        检查Ollama服务是否可用

        Returns:
            True如果服务正常，False否则
        """
        try:
            session = await self._ensure_session()
            async with session.get(f"{self.base_url}/api/tags", timeout=ClientTimeout(total=5)) as response:
                if response.status == 200:
                    data = await response.json()
                    models = [m.get("name", "") for m in data.get("models", [])]
                    logger.info("Ollama healthy. Available models: %s", models)
                    return True
                return False
        except Exception as e:
            logger.warning("Ollama health check failed: %s", e)
            return False

    def get_stats(self) -> Dict[str, Any]:
        """
        获取客户端统计信息

        Returns:
            统计信息字典
        """
        return {
            "base_url": self.base_url,
            "model": self.model,
            "timeout": self.timeout,
            "max_retries": self.max_retries,
            "pool_size": self.connection_pool_size,
            "session_active": self._session is not None and not self._session.closed,
        }
