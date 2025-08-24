import asyncio
import json
import websockets
import base64
import os
from astrbot.api.platform import AstrBotMessage
from astrbot import logger
class MessageServer:
    def __init__(self, host: str = '0.0.0.0', port: int = 8080, adapter=None, on_received=None):
        self.host = host
        self.port = port
        self.clients = set()
        self.adapter = adapter  # 保存适配器引用
        self.on_received = on_received  # 消息接收回调函数
        # 存储客户端ID与websocket的映射关系
        self.client_websockets = {}
        # 存储websocket与客户端ID的映射关系
        self.websocket_client = None

    async def send_text(self, to: str, message: str):
        """向指定客户端发送文本消息"""
        if to in self.client_websockets:
            websocket = self.client_websockets[to]
            try:
                await websocket.send(json.dumps({
                    'type': 'text',
                    'content': message
                }))
                logger.info(f'[MessageServer] 发送文本到 {to}: {message}')
            except Exception as e:
                logger.info(f'[MessageServer] 发送文本失败: {e}')
        else:
            logger.info(f'[MessageServer] 未找到客户端: {to}')

    async def send_image(self, to: str, image_path: str):
        """向指定客户端发送图片消息（base64格式）"""
        if to in self.client_websockets:
            websocket = self.client_websockets[to]
            try:
                # 检查文件是否存在
                if not os.path.exists(image_path):
                    logger.info(f'[MessageServer] 图片文件不存在: {image_path}')
                    return

                # 读取图片文件并转换为base64
                with open(image_path, 'rb') as f:
                    image_data = f.read()
                    base64_data = base64.b64encode(image_data).decode('utf-8')

                # 获取图片扩展名
                _, ext = os.path.splitext(image_path)
                ext = ext.lower()[1:]  # 去掉点号
                if ext == 'jpg':
                    ext = 'jpeg'

                # 构建data URL
                data_url = f'data:image/{ext};base64,{base64_data}'

                await websocket.send(json.dumps({
                    'type': 'image',
                    'data_url': data_url
                }))
                print(f'[MessageServer] 发送图片到 {to}: {image_path} (已转换为base64)')
            except Exception as e:
                print(f'[MessageServer] 发送图片失败: {e}')
        else:
            print(f'[MessageServer] 未找到客户端: {to}')

    async def register(self, websocket):
        self.clients.add(websocket)
        # 暂时使用remote_address作为客户端ID
        client_id = str(websocket.remote_address)
        self.client_websockets[client_id] = websocket
        self.websocket_client = websocket
        print(f'新客户端连接: {websocket.remote_address}, 客户端ID: {client_id}')

    async def unregister(self, websocket):
        self.clients.remove(websocket)
        if websocket in self.client_websockets:
            client_id = self.client_websockets[websocket]
            del self.client_websockets[client_id]
            self.websocket_client = None
            print(f'客户端断开连接: {websocket.remote_address}, 客户端ID: {client_id}')
        else:
            print(f'客户端断开连接: {websocket.remote_address}')



    async def handle_message(self, websocket):
        """处理WebSocket连接和消息"""
        await self.register(websocket)
        try:
            async for message in websocket:
                logger.info(f'[MessageServer] 收到消息: {message}')
                # 解析消息
                data = json.loads(message)
                # 添加客户端ID到数据中，以便后续1对1回复
                client_id = self.client_websockets.get(websocket, str(websocket.remote_address))
                data['client_id'] = client_id
                # 调用回调函数处理消息
                if self.on_received:
                    await self.on_received(data)
                # 发送响应
                response = {'status': 'success', 'type': 'MESSAGE_COMMIT'}
                await websocket.send(json.dumps(response))
        finally:
            await self.unregister(websocket)

    async def start(self):
        logger.info(f'启动消息服务器在 {self.host}:{self.port}')
        server = await websockets.serve(
            self.handle_message, self.host, self.port
        )
        await server.wait_closed()


async def main():
    server = MessageServer()
    await server.start()


if __name__ == '__main__':
    asyncio.run(main())