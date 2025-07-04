from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api import logger
from astrbot.core.config.astrbot_config import AstrBotConfig
from astrbot.api.message_components import *
import aiohttp

from data.plugins.astrbot_plugin_n8n.videos_analysis.main import hybird_videos_analysis


@register("astrbot_plugin_n8n", "Wanxp", "一个调用n8n webhook插件", "1.0.0")
class MyPlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config = config
        self.media_analyzer = hybird_videos_analysis(context, config.get('n8n'))

    async def initialize(self):
        """可选择实现异步的插件初始化方法，当实例化该插件类之后会自动调用该方法。"""

    # 注册指令的装饰器。指令名为 n8n 。注册成功后，发送 `/n8n` 就会触发这个指令，并回复 `你好, {user_name}!`

    # @filter.command("nb")
    # async def call_n8n(self, event: AstrMessageEvent):
    #     """这是一个 调用n8n 的指令"""
    #     message_str, sender_name, url, username, password = self.message_str(event)
    #     # 移除掉第一个'n8n'
    #     message_str = message_str.replace(
    #         "n", "", 1
    #     ).strip()  # 去掉指令名，保留用户输入的内容
    #
    #     if message_str is None:
    #         yield event.plain_result("请提供 n8n 的调用内容。")
    #         return
    #     message_str = f'ob: {message_str}'
    #     await self.on_message(message_str, sender_name, url, username, password, event)

    @filter.command("n8n")
    async def call_n8n(self, event: AstrMessageEvent):
        message, sender_name, url, username, password = self.get_message_str(event)
        if message is None:
            event.plain_result(
                "请提供 n8n 的调用内容。"
            )
            yield event
        message = message.replace(
            "n8n", "", 1
        ).strip()  # 去掉指令名，保留用户输入的内容
        logger.info(f"用户 {sender_name} ({event.session_id}) 调用 n8n 插件，内容: {message}")

        event_return = await self.on_message(message, sender_name, url, username, password, event)
        yield event_return

    def get_message_str(self, event: AstrMessageEvent):
        """这是一个 调用n8n 的指令"""  # 这是 handler 的描述，将会被解析方便用户了解插件内容。建议填写。
        sender_name = event.get_sender_name()
        message = event.message_str  # 用户发的纯文本消息字符串
        url = self.config["n8n"].get(
            "n8n_webhook_url"
        )  # 从配置中获取 n8n 的 webhook URL
        adminIds = self.config["n8n"].get(
            "adminIds"
        )  # 从配置中获取 n8n 的管理员 ID 列表
        admin_ids = (
            adminIds.split(",") if adminIds else []
        )  # 如果配置中有 adminIds ，则将其分割成列表
        if admin_ids is None or len(admin_ids) == 0:
            logger.error(
                "n8n 插件未配置 adminIds ，请在n8n插件配置文件中 n8n.adminIds 配置值"
            )
            event.plain_result(
                "n8n 插件未配置 adminIds ，请在n8n插件配置文件中 n8n.adminIds 配置发送者的id,多个则以逗号分隔"
            )
            return None, None, None, None, None
        isAdmin = False
        print(f"当前用户 {sender_name} ({event.session_id}) 尝试调用 n8n 插件")
        for admin_id in admin_ids:
            if str(event.session_id).__contains__(admin_id.strip()):
                isAdmin = True
                break
        if isAdmin is False:
            logger.warning(
                f"用户 {sender_name} ({event.session_id}) 没有权限调用 n8n 插件"
            )
            event.plain_result(
                 f"用户 {sender_name} ({event.session_id}) 没有权限调用 n8n 插件"
            )
            return None, None, None, None, None
        username = self.config["n8n"].get("username")  # 从配置中获取 n8n 的 webhook URL
        password = self.config["n8n"].get("password")  # 从配置中获取 n8n 的 webhook URL
        return message, sender_name, url, username, password



    async def on_message(self,message_str, sender_name, url, username, password, event: AstrMessageEvent):
        try:
            file_urls, file_type = await self.media_analyzer.auto_parse(event, message_str)
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url=url,
                    auth=aiohttp.BasicAuth(username, password),
                    json={
                        "message": message_str,
                        "senderName": sender_name,
                        "fileType": file_type if file_type else 'None',
                        "fileUrls": file_urls if file_urls else [],
                    },
                ) as response:
                    if response.status != 200:
                        logger.error(f"调用 n8n webhook 失败: {await response.text()}")
                        return event.plain_result(
                            "调用 n8n webhook 失败，请检查配置或网络连接。"
                        )


                    logger.info(f"调用 n8n webhook 成功: {await response.text()}")
                    response_data = await response.json()

                    if "data" in response_data:
                        result = response_data["data"]
                        return event.plain_result(f"n8n 返回结果: {result}")
                    else:
                        logger.warning("n8n 返回结果中没有 'data' 字段")
                        return event.plain_result(
                            f"n8n调用成功,响应缺少data字段,具体响应如下:{await response.text()}"
                        )

        except aiohttp.ClientError as e:
            logger.error(f"aiohttp 请求错误: {e}")
            return event.plain_result(
                f"调用 n8n webhook 时发生错误，请检查网络连接。错误详情: {str(e)}"
            )

        except Exception as e:
            logger.error(f"未捕获的异常: {e}")
            return event.plain_result(
                f"调用 n8n webhook 时发生未捕获的异常。错误详情: {str(e)}"
            )

    async def terminate(self):
        """可选择实现异步的插件销毁方法，当插件被卸载/停用时会调用。"""
