import asyncio
import json
import websockets
from typing import AsyncIterator, List, Dict, Any, Callable, Literal, Union, Optional
from loguru import logger

from ..output_types import (
    BaseOutput,
    SentenceOutput,
    AudioOutput,
    DisplayText,
    Actions,
)
from ..input_types import BaseInput, BatchInput, TextData, TextSource
from .agent_interface import AgentInterface
from ..transformers import (
    sentence_divider,
    actions_extractor,
    tts_filter,
    display_processor,
)
from ...config_manager import TTSPreprocessorConfig
from ...mcpp.tool_manager import ToolManager
from ...mcpp.tool_executor import ToolExecutor


def batch_input_to_dict(batch: BatchInput) -> dict:
    """把 BatchInput 转换为可 JSON 序列化的 dict."""
    return {
        "texts": [
            {
                "source": text.source.value,
                "content": text.content,
                "from_name": text.from_name,
            }
            for text in batch.texts
        ],
        "images": [
            {
                "source": img.source.value,
                "data": img.data,
                "mime_type": img.mime_type,
            }
            for img in (batch.images or [])
        ],
        "files": [
            {
                "name": f.name,
                "data": f.data,
                "mime_type": f.mime_type,
            }
            for f in (batch.files or [])
        ],
        "metadata": batch.metadata or {},
    }


def parse_output_message(msg: str) -> BaseOutput:
    """
    将 WebSocket 返回的 JSON 消息解析成 BaseOutput 子类
    这里假设服务端会返回结构大致如下：
    {
        "type": "message", 
        "session_id": "2025-08-24_06-21-12_29d0dea489a840e3877d1cb3611849f2", 
        "content": "", 
        "message_chain": [
            {"type": "image", "file": "file:///C:\\Users\\Administrator\\Documents\\GitHub\\AstrBot\\data\\memes_data\\memes\\morning\\1739434673_1.jpg"},
            {"type": "plain", "content": "这是一张图片"}
            ]
    }
    """
    data = json.loads(msg)

    actions = Actions(
        expressions=data.get("actions", {}).get("expressions"),
        pictures=data.get("actions", {}).get("pictures"),
        sounds=data.get("actions", {}).get("sounds"),
    )

    if data.get("type") == "sentence":
        return SentenceOutput(
            display_text=DisplayText(**data["display_text"]),
            tts_text=data.get("tts_text", ""),
            actions=actions,
        )
    elif data.get("type") == "audio":
        return AudioOutput(
            audio_path=data["audio_path"],
            display_text=DisplayText(**data["display_text"]),
            transcript=data.get("transcript", ""),
            actions=actions,
        )
    else:
        raise ValueError(f"Unknown output type from server: {data}")


class WebSocketLLMClient:
    """WebSocket 客户端，负责与远程 LLM 服务通信（长连接模式）。"""

    def __init__(self, uri: str, reconnect_interval: int = 5):
        self.uri = uri
        self.reconnect_interval = reconnect_interval  # 重连间隔（秒）
        self.ws = None  # WebSocket 连接对象
        self.connection_status = "disconnected"  # 连接状态
        self.lock = asyncio.Lock()  # 用于保证线程安全

    async def connect(self):
        """建立 WebSocket 连接。"""
        if self.connection_status == "connected":
            logger.info("WebSocket is already connected.")
            return

        try:
            logger.info(f"Connecting to WebSocket server at {self.uri}...")
            self.ws = await websockets.connect(self.uri)
            self.connection_status = "connected"
            logger.info("WebSocket connection established successfully.")
        except Exception as e:
            self.connection_status = "disconnected"
            logger.error(f"Failed to connect to WebSocket server: {e}")
            raise

    async def disconnect(self):
        """关闭 WebSocket 连接。"""
        if self.ws and self.connection_status == "connected":
            try:
                await self.ws.close()
                self.connection_status = "disconnected"
                self.ws = None
                logger.info("WebSocket connection closed.")
            except Exception as e:
                logger.error(f"Error closing WebSocket connection: {e}")

    async def ensure_connection(self):
        """确保 WebSocket 连接已建立。如果连接断开，尝试重连。"""
        if self.connection_status != "connected":
            await self.connect()


    async def chat_completion(
        self, input_data: BaseInput, system: str = "", session_id: str = "default_session"
    ) -> AsyncIterator[BaseOutput]:
        async with self.lock:
            try:
                await self.ensure_connection()

                # 准备并发送请求
                payload = {
                    "bot_id":"open_llm_vtuber_bot",
                    "session_id": session_id,
                    "channel_type":"FRIEND",
                    "userid":"815049548",
                    "username":"YakumoAki",
                    "messages":  batch_input_to_dict(input_data),
                }
                payload_str = json.dumps(payload, ensure_ascii=False)
                logger.info(f"Sending message to server: {payload_str}")
                await self.ws.send(payload_str)

                logger.info("Waiting for response from server...")
                message_count = 0
                max_messages = 10  # 设置最大消息数限制

                async for msg in self.ws:
                    message_count += 1
                    logger.info(f"Received message {message_count} from server")
                    
                    try:
                        data = json.loads(msg)
                        logger.info(f"Message content: {data}")
                        if data.get("type") == "MESSAGE_COMMIT":
                            logger.info("MESSAGE_COMMIT to server queue, writing response")

                        # 检查是否为结束消息
                        elif data.get("type") == "MESSAGE_END":
                            logger.info("Received end message, stopping")
                            break
                        elif data.get("type") == "text":
                            yield data['content']
                        elif data.get("type") == "message":
                            output = data['file']
                            
                            logger.info(f"get image message: {output}")
                        else:
                            logger.info(f"get unknow message: {data}")
                    except json.JSONDecodeError:
                        logger.error(f"Invalid JSON message: {msg}")
                    except Exception as e:
                        logger.error(f"Failed to process message: {msg}, error={e}")

                    # 防止无限接收
                    if message_count >= max_messages:
                        logger.warning(f"Reached max message limit ({max_messages}), stopping")
                        break

            except websockets.exceptions.WebSocketException as e:
                logger.error(f"WebSocket connection error: {e}")
                self.connection_status = "disconnected"
                # 尝试重连
                logger.info(f"Trying to reconnect in {self.reconnect_interval} seconds...")
                await asyncio.sleep(self.reconnect_interval)
                try:
                    await self.connect()
                    logger.info("Reconnected successfully.")
                except Exception as re_e:
                    logger.error(f"Failed to reconnect: {re_e}")
                raise
            except Exception as e:
                logger.error(f"Unexpected error in chat_completion: {e}")
                raise
        



class AstrAgent(AgentInterface):
    """通过 WebSocket 连接到 AstrBot 服务的 Agent 实现。"""

    def __init__(
        self,
        llm_url: str,
        system: str,
        live2d_model,
        tts_preprocessor_config: TTSPreprocessorConfig = None,
        faster_first_response: bool = True,
        segment_method: str = "pysbd",
        use_mcpp: bool = False,
        interrupt_method: Literal["system", "user"] = "user",
        tool_prompts: Dict[str, str] = None,
        tool_manager: Optional[ToolManager] = None,
        tool_executor: Optional[ToolExecutor] = None,
        mcp_prompt_string: str = "",
        reconnect_interval: int = 5,
    ):
        """初始化 Agent 与 LLM 配置。"""
        super().__init__()
        self._live2d_model = live2d_model
        self._tts_preprocessor_config = tts_preprocessor_config
        self._faster_first_response = faster_first_response
        self._segment_method = segment_method
        self._use_mcpp = use_mcpp
        self.interrupt_method = interrupt_method
        self._tool_prompts = tool_prompts or {}
        self._interrupt_handled = False

        self._tool_manager = tool_manager
        self._tool_executor = tool_executor
        self._mcp_prompt_string = mcp_prompt_string
        self._reconnect_interval = reconnect_interval

        # 设置 LLM 客户端
        self._llm = WebSocketLLMClient(uri=llm_url, reconnect_interval=reconnect_interval)
        
        # self._system_prompt = system
        self._system_prompt = ''

        logger.info("AstrAgent initialized with WebSocket LLM client.")

    async def start(self):
        """启动 Agent，建立 WebSocket 连接。"""
        await self._llm.connect()
        logger.info("AstrAgent started and WebSocket connection established.")

    async def stop(self):
        """停止 Agent，关闭 WebSocket 连接。"""
        await self._llm.disconnect()
        logger.info("AstrAgent stopped and WebSocket connection closed.")

    async def chat(self, input_data: BaseInput) -> AsyncIterator[BaseOutput]:
        """
        与 Agent 异步聊天。

        Args:
            input_data: BaseInput - 用户输入数据

        Returns:
            AsyncIterator[BaseOutput] - Agent 输出流
        """
        self.reset_interrupt()

        try:
            # 创建带装饰器的聊天函数
            chat_func = self._create_chat_function()
            async for output in chat_func(input_data):
                yield output
        except Exception as e:
            logger.error(f"Chat error: {e}")
            # 创建错误响应
            error_output = SentenceOutput(
                display_text=DisplayText(text=f"Error: {str(e)}", name="System"),
                tts_text=f"抱歉，发生错误：{str(e)}",
                actions=Actions(),
            )
            yield error_output

    def handle_interrupt(self, heard_response: str) -> None:
        """
        处理用户中断。

        Args:
            heard_response: str - 中断前听到的响应部分
        """
        logger.warning(f"Agent: Interrupted after response={heard_response}")
        self._interrupt_handled = True

    def set_memory_from_history(self, conf_uid: str, history_uid: str) -> None:
        """
        从聊天历史加载 Agent 的工作记忆

        Args:
            conf_uid: str - 配置 ID
            history_uid: str - 历史 ID
        """
        logger.info(
            f"AstrAgent: set_memory_from_history called with conf_uid={conf_uid}, history_uid={history_uid}"
        )
        # 存储 history_uid 供后续使用
        self._history_uid = history_uid
        # AstrAgent 暂不支持记忆功能

    def reset_interrupt(self) -> None:
        """重置中断标志。"""
        self._interrupt_handled = False

    def _create_chat_function(self) -> Callable:
        """创建带装饰器的聊天函数。"""
        @tts_filter(self._tts_preprocessor_config)
        @display_processor()
        @actions_extractor(self._live2d_model)
        @sentence_divider(
            faster_first_response=self._faster_first_response,
            segment_method=self._segment_method,
            valid_tags=["think"],
        )
        async def chat_function(input_data: BatchInput) -> AsyncIterator[BaseOutput]:
            """处理聊天请求并返回响应流。"""
            # 通过 WebSocket 发送请求并接收响应
            # 使用存储的 history_uid 作为 session_id
            session_id = getattr(self, '_history_uid', 'default_session')
            async for output in self._llm.chat_completion(input_data, self._system_prompt, session_id):
                if self._interrupt_handled:
                    logger.info("Chat interrupted by user.")
                    break
                yield output

        return chat_function

    def start_group_conversation(
        self, human_name: str, ai_participants: List[str]
    ) -> None:
        """
        开始群聊。

        Args:
            human_name: str - 人类名称
            ai_participants: List[str] - AI 参与者列表
        """
        logger.info(f"Starting group conversation with {human_name} and {ai_participants}")
        # 暂不实现群聊功能
