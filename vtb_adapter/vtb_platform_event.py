from astrbot.api.event import AstrMessageEvent, MessageChain
from astrbot.api.platform import AstrBotMessage, PlatformMetadata
from astrbot.api.message_components import Plain, Image
from astrbot.core.utils.io import download_image_by_url

from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.provider import ProviderRequest
from astrbot import logger
from .server import MessageServer

class VtbPlatformEvent(AstrMessageEvent):
    def __init__(self, message_str: str, message_obj: AstrBotMessage, platform_meta: PlatformMetadata, session_id: str,server: MessageServer):
        super().__init__(message_str, message_obj, platform_meta, session_id)
        self.server = server
        self.sender_id = session_id  # 存储sender_id以便后续使用
    
    def get_sender_id(self):
        """返回发送者ID，用于1对1消息发送"""
        return self.sender_id
        
    async def send(self, message: MessageChain):
        for i in message.chain: # 遍历消息链
            if isinstance(i, Plain): # 如果是文字类型的
                await self.server.send_text(to=self.get_sender_id(), message=i.text)
            elif isinstance(i, Image): # 如果是图片类型的 
                img_url = i.file
                img_path = ""
                # 处理不同类型的图片路径
                if img_url.startswith("file:///"):
                    img_path = img_url[8:]
                elif i.file and i.file.startswith("http"):
                    try:
                        img_path = await download_image_by_url(i.file)
                    except Exception as e:
                        logger.info(f"[VtbPlatformEvent] 下载图片失败: {e}")
                        img_path = img_url
                else:
                    img_path = img_url

                await self.server.send_image(to=self.get_sender_id(), image_path=img_path)
        await self.server.websocket_client.send(json.dumps({
            'type': 'MESSAGE_END'
        }))
        await super().send(message) # 执行父类的 send 方法