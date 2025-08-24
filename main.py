from astrbot.api.star import Context, Star, register
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.provider import ProviderRequest

@register("vtb_adapter", "YakumoAki", "open llm vtb 适配器", "0.0.1")
class VtbAdapterPlugin(Star):
    def __init__(self, context: Context):
        from .vtb_adapter.vtb_adapter import VtbPlatformAdapter # noqa 
        @filter.on_llm_request()
        async def my_custom_hook_1(self, event: AstrMessageEvent, req: ProviderRequest): # 请注意有三个参数
            print(req) # 打印请求的文本
            req.system_prompt +="""
## Expressions
In your response, use the keywords provided below to express facial expressions or perform actions with your Live2D body.
Here are all the expression keywords you can use. Use them regularly:
- [neutral], [anger], [disgust], [fear], [joy], [smirk], [sadness], [surprise],
## Examples
Here are some examples of how to use expressions in your responses:
"Hi! [expression1] Nice to meet you!"
"[expression2] That's a great question! [expression3] Let me explain..."
Note: you are only allowed to use the keywords explicity listed above. Don't use keywords unlisted above. Remember to include the brackets `[]`
If you received `[interrupted by user]` signal, you were interrupted.
"""