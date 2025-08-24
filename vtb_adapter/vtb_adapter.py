import asyncio
import json
import base64
import os
import uuid

from astrbot.api.platform import Platform, AstrBotMessage, MessageMember, PlatformMetadata, MessageType
from astrbot.api.event import MessageChain
from astrbot.api.message_components import Plain, Image, Record # 消息链中的组件，可以根据需要导入
from astrbot.core.platform.astr_message_event import MessageSesion, AstrMessageEvent
from astrbot import logger
from astrbot.api.platform import register_platform_adapter
from .server import MessageServer
from .vtb_platform_event import VtbPlatformEvent
            
# 注册平台适配器。第一个参数为平台名，第二个为描述。第三个为默认配置。
@register_platform_adapter("open_llm_vtb", "Open LLM VTB 适配器", default_config_tmpl={
    "server_host": "0.0.0.0",
    "server_port": 8765
})
class VtbPlatformAdapter(Platform):

    def __init__(self, platform_config: dict, platform_settings: dict, event_queue: asyncio.Queue) -> None:
        super().__init__(event_queue)
        self.config = platform_config
        self.settings = platform_settings
        self.server = None
    
    async def send_by_session(self, session: MessageSesion, message_chain: MessageChain):
        # 实现消息发送逻辑
        logger.info(f"[VtbPlatformAdapter] 发送消息到会话 {session.session_id}")
        
        # 构建消息内容
        message_data = {
            'type': 'message',
            'session_id': session.session_id,
            'content': '',
            'message_chain': []
        }
        
        # 处理消息链
        for component in message_chain.chain:
            if isinstance(component, Plain):
                message_data['content'] += component.text
                message_data['message_chain'].append({
                    'type': 'plain',
                    'text': component.text
                })
            elif isinstance(component, Image):
                message_data['message_chain'].append({
                    'type': 'image',
                    'file': component.file
                })
        
        # 发送消息到所有连接的客户端
        if self.server and self.server.clients:
            for client in self.server.clients:
                try:
                    await client.send(json.dumps(message_data))
                    print(f"[VtbPlatformAdapter] 消息已发送到客户端 {client.remote_address}")
                except Exception as e:
                    print(f"[VtbPlatformAdapter] 发送消息失败: {e}")
        
        await super().send_by_session(session, message_chain)
    
    def meta(self) -> PlatformMetadata:
        return PlatformMetadata(
            "open_llm_vtb",
            "Open LLM VTB 适配器",
        )

    async def run(self):
        """启动适配器和WebSocket服务器"""
        logger.info("[VtbPlatformAdapter] 启动适配器")

        # 从配置中获取服务器地址和端口
        host = self.config.get("server_host", "0.0.0.0")
        port = self.config.get("server_port", 8765)
        
        async def on_received(data):
            logger.info(data)
            abm = await self.convert_message(data=data) # 转换成 AstrBotMessage
            await self.handle_msg(abm) 

        # 初始化并启动WebSocket服务器
        self.server = MessageServer(host=host, port=port, adapter=self, on_received=on_received)
        logger.info(f"[VtbPlatformAdapter] 启动WebSocket服务器在 {host}:{port}")
        await self.server.start()

    async def convert_message(self, data: dict) -> AstrBotMessage:
        """将平台消息转换为AstrBotMessage"""
        abm = AstrBotMessage()
        abm.type = MessageType.FRIEND_MESSAGE
        abm.sender = MessageMember(user_id=data['userid'], nickname=data['username'])
        abm.message_str = str(data['messages']) # 纯文本消息。重要！
        abm.raw_message = data
        
        abm.self_id = data.get('bot_id', 'vtb_bot')
        # 使用client_id作为session_id，确保1对1通信
        abm.session_id = data.get('client_id', data.get('session_id', '1'))
        abm.message_id = data.get('msg_id', str(asyncio.get_event_loop().time()))
        
        abm.message = []
        for plain in data['messages']['texts']:
            abm.message.append(Plain(text=plain['content']))
        # 处理图片消息
        for image in data['messages']['images']:
            # 获取base64图片数据
            base64_data = image['data']
            if base64_data.startswith('data:'):
                # 解析data URL
                header, encoded = base64_data.split(',', 1)
                image_data = base64.b64decode(encoded)

                # 获取图片格式
                mime_type = image.get('mime_type', 'image/jpeg')
                image_format = mime_type.split('/')[1] if '/' in mime_type else 'jpeg'

                # 生成唯一文件名
                filename = f"vtb_image_{uuid.uuid4()}.{image_format}"
                # 确保保存目录存在
                os.makedirs('temp_images', exist_ok=True)
                file_path = os.path.join('temp_images', filename)

                # 保存图片到本地
                with open(file_path, 'wb') as f:
                    f.write(image_data)
                logger.info(f"[VtbPlatformAdapter] 图片已保存到: {file_path}")

                # 创建Image对象并添加到消息链
                abm.message.append(Image(file=file_path))
            else:
                # 如果不是data URL格式，直接使用
                abm.message.append(Image(file=base64_data))

        return abm



    async def handle_msg(self, message: AstrBotMessage):
        """处理消息并提交事件"""
        message_event = VtbPlatformEvent(
            message_str=message.message_str,
            message_obj=message,
            platform_meta=self.meta(),
            session_id=message.session_id,
            server=self.server
        )
        self.commit_event(message_event) # 提交事件到事件队列
        logger.info(f"[VtbPlatformAdapter] 消息事件已提交: {message.session_id}")