# 🎮 Open LLM TVB 适配器


## 🌟 适配器简介  
Open LLM TVB 适配器是一个为 AstrBot 设计的插件，用于连接 AstrBot 与 Open LLM VTuber 平台。该插件支持机器人与虚拟主播进行实时交互，实现消息接收。  



## 🚀 快速使用指南  
### 1. 插件安装  
- 进入 AstrBot 插件市场，搜索并安装 **「astrbot_plugin_vtb_adapter」**。  
- 同时还需要在Open LLM VTuber中添加对应agent


### 2. 适配器配置  
- 安装完成后，前往 **消息平台 → 新增适配器 → 选择 Open LLM TVB**（若选项缺失，尝试重启 AstrBot 或检查插件安装状态）。  


### 3. Open LLM TVB 配置  
#### 为Open LLM VTuber安装"websocket-client>=1.8.0",
#### 配置Open LLM VTuber 
 1. 可以直接将Open-LLM-VTuber\src 文件夹直接复制进Open LLM VTuber项目中替换，然后在config.yaml中agent_config.agent_settings添加如下配置，conversation_agent_choice填入'astr_agent'。
```yaml
  agent_config:
    conversation_agent_choice: 'astr_agent' # 对话代理选择

    agent_settings:
      # 新添加配置项目
      astr_agent:
        # 通过 WebSocket 连接到 AstrBot 服务的 AI 代理
        llm_url: 'ws://localhost:8080/ws' # AstrBot 服务的 WebSocket URL
        # 是否在第一句回应时遇上逗号就直接生成音频以减少首句延迟
        faster_first_response: True
        # 句子分割方法：'regex' 或 'pysbd'
        segment_method: 'pysbd'
        # 是否使用 MCP（Model Context Protocol）
        use_mcpp: False
        # 中断方法：'system' 或 'user'
        interrupt_method: 'user'
```
 2. 如果不直接替换，除了需要像1中一样修改conf.yml，还需要修改如下文件：
   - 将Open-LLM-VTuber\src\open_llm_vtuber\agent\agents\astr_agent.py 复制到Open LLM VTuber 同一位置
   - 修改Open-LLM-VTuber\src\open_llm_vtuber\agent\agent_factory.py，添加如下代码：
```python
        # 需要新添加的
        from .agents.astr_agent import AstrAgent

        # 原有代码，在这个后面添加
        elif conversation_agent_choice == "letta_agent":
            settings = agent_settings.get("letta_agent", {})
            return LettaAgent(
                live2d_model=live2d_model,
                id=settings.get("id"),
                tts_preprocessor_config=tts_preprocessor_config,
                faster_first_response=settings.get("faster_first_response"),
                segment_method=settings.get("segment_method"),
                host=settings.get("host"),
                port=settings.get("port"),
            )
        # 新添加的
        elif conversation_agent_choice == "astr_agent":
            # Get the AstrAgent settings
            astr_agent_settings: dict = agent_settings.get("astr_agent", {})
            llm_url: str = astr_agent_settings.get("llm_url", "ws://localhost:8080/ws")

            if not llm_url:
                raise ValueError("LLM URL not specified for astr_agent")

            tool_prompts = kwargs.get("system_config", {}).get("tool_prompts", {})

            # Extract MCP components/data needed by AstrAgent from kwargs
            tool_manager: Optional[ToolManager] = kwargs.get("tool_manager")
            tool_executor: Optional[ToolExecutor] = kwargs.get("tool_executor")
            mcp_prompt_string: str = kwargs.get("mcp_prompt_string", "")

            # Create the agent with the LLM and live2d_model
            return AstrAgent(
                llm_url=llm_url,
                system=system_prompt,
                live2d_model=live2d_model,
                tts_preprocessor_config=tts_preprocessor_config,
                faster_first_response=astr_agent_settings.get("faster_first_response", True),
                segment_method=astr_agent_settings.get("segment_method", "pysbd"),
                use_mcpp=astr_agent_settings.get("use_mcpp", False),
                interrupt_method=astr_agent_settings.get("interrupt_method", "user"),
                tool_prompts=tool_prompts,
                tool_manager=tool_manager,
                tool_executor=tool_executor,
                mcp_prompt_string=mcp_prompt_string,
            )
```
   - 修改Open-LLM-VTuber\src\open_llm_vtuber\config_manager\agent.py，在第203行添加"astr_agent"
```python
203           "basic_memory_agent", "mem0_agent", "hume_ai_agent", "letta_agent", "astr_agent"
```

#### 🔧 配置连接信息  
- 在适配器配置页面，填写以下信息：  
  1. **服务器地址**：WebSocket 服务器地址（默认为 `ws://localhost:8765`）  
  2. **服务器端口**：WebSocket 服务器端口（默认为 `8765`）  
  3. 点击「测试连接」确保与 Open LLM TVB 服务正常通信。  



## ⚠️ 注意事项  
- 使用当连接到AstrBot时，需要先启动AstrBot。
- 当连接到AstrBot后Open LLM VTuber中的人格设定将不再生效，将使用AstrBot。
- **连接状态检查**：确保适配器显示为「已连接」，若配置后连接失败，可尝试重启适配器或检查 Open LLM TVB 服务状态。  
- **防火墙设置**：确保服务器端口（默认 8765）已在防火墙中开放，避免因网络问题导致连接失败。  


## 📝 更新日志 
- **0.0.0**：发布 Open LLM TVB 适配器，支持基础消息交互


## 🙏 致谢

*   感谢 **AstrBot 核心开发团队** 提供的强大平台和技术支持。
*   感谢 **Open LLM TVB 项目组** 提供的接口和文档支持。
*   感谢所有在社区中提出宝贵意见和反馈的用户。



## 📚 支持与帮助  
- 发现 Bug？有好点子？请随时通过 [GitHub Issues](https://github.com/wuyan1003/astrbot_plugin_vtb_adapter/issues) 告诉我们。每一条反馈我们都会认真对待。
