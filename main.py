from aiocqhttp import CQHttp
from astrbot.api.event import filter
from astrbot.api.star import Context, Star, register
from astrbot.core import AstrBotConfig
from astrbot.core.platform.sources.aiocqhttp.aiocqhttp_message_event import (
    AiocqhttpMessageEvent,
)
from astrbot.core.star.filter.event_message_type import EventMessageType
from astrbot import logger

@register(
    "astrbot_plugin_notice",
    "Zhalslar",
    "通知插件（告状插件）",
    "1.0.0",
    "https://github.com/Zhalslar/astrbot_plugin_notice",
)
class RereadPlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        # 管理员列表
        self.admins_id: list = context.get_config().get("admins_id", [])
        # 管理群
        self.manage_group: str = config.get("manage_group", 114514)
        # 控制开关
        self.group_ban_notice: bool = config.get("ban_notice", True)
        self.group_admin_notice: bool = config.get("admin_notice", True)
        self.group_change_notice: bool = config.get("decrease_notice", True)

    @staticmethod
    def convert_duration(duration):
        """格式化时间"""
        days = duration // 86400
        hours = (duration % 86400) // 3600
        minutes = (duration % 3600) // 60
        seconds = duration % 60

        result = []
        if days > 0:
            result.append(f"{days}天")
        if hours > 0:
            result.append(f"{hours}小时")
        if minutes > 0:
            result.append(f"{minutes}分钟")
        if seconds > 0 or not result:
            result.append(f"{seconds}秒")

        return " ".join(result)

    async def get_operator_name(self, client, group_id, operator_id):
        """获取操作者名称"""
        operator_info = await client.get_group_member_info(
            group_id=group_id, user_id=operator_id
        )
        operator_name = operator_info.get("card") or operator_info.get("nickname")
        return operator_name

    @filter.event_message_type(EventMessageType.GROUP_MESSAGE)
    async def on_notice(self, event: AiocqhttpMessageEvent):
        """监听事件"""
        raw_message = getattr(event.message_obj, "raw_message", None)

        if (
            not raw_message
            or not isinstance(raw_message, dict)
            or raw_message.get("post_type") == "message"
        ):
            return

        client = event.bot
        self_id = int(event.get_self_id())
        group_id = raw_message.get("group_id", 0)
        user_id = raw_message.get("user_id", 0)

        # 只处理Bot相关的notice事件
        if raw_message.get("post_type") != "notice" or user_id != self_id:
            return

        group_info = await client.get_group_info(group_id=group_id)
        group_name = group_info.get("group_name")
        operator_id = raw_message.get("operator_id", 0)

        reply = ""

        # 群禁言事件
        if self.group_ban_notice and raw_message.get("notice_type") == "group_ban":
            duration = raw_message.get("duration", 0)
            operator_name = await self.get_operator_name(client, group_id, operator_id)
            if duration:
                reply = f"呜呜ww..主人，我在 {group_name}({group_id}) 被 {operator_name} 禁言了{self.convert_duration(duration)}"
            else:
                reply = (
                    f"好耶！{operator_name} 在 {group_name}({group_id}) 解除了我的禁言"
                )

        # 群管理员变动
        elif (
            self.group_admin_notice and raw_message.get("notice_type") == "group_admin"
        ):
            if raw_message.get("sub_type") == "set":
                reply = f"哇！我成为了 {group_name}({group_id}) 的管理员"
            else:
                reply = f"呜呜ww..我在 {group_name}({group_id}) 的管理员被撤了"

        # 群成员减少事件
        elif (
            self.group_change_notice
            and raw_message.get("notice_type") == "group_decrease"
            and raw_message.get("sub_type") == "kick_me"
        ):
            operator_name = await self.get_operator_name(client, group_id, operator_id)
            reply = f"呜呜ww..我被 {operator_name} 踢出了 {group_name}({group_id})"

        # 群成员增加事件
        elif (
            self.group_change_notice
            and raw_message.get("notice_type") == "group_increase"
            and raw_message.get("sub_type") == "invite"
        ):
            operator_name = await self.get_operator_name(client, group_id, operator_id)
            reply = f"主人..我被 {operator_name} 拉进了 {group_name}({group_id})"

        if reply:
            await self.send_reply(client, reply)
            await self.check_messages(client, group_id)
            event.stop_event()

    async def send_reply(self, client: CQHttp, message):
        "发送回复消息"
        if self.manage_group:
            await client.send_group_msg(
                group_id=int(self.manage_group), message=message
            )
        elif self.admins_id:
            for admin_id in self.admins_id:
                if admin_id.isdigit():
                    await client.send_private_msg(
                        user_id=int(admin_id), message=message
                    )

    async def check_messages(self, client: CQHttp, target_group_id: int):
        """
        抽查指定群聊的消息
        """
        # 获取群聊历史消息
        result: dict = await client.get_group_msg_history(group_id=target_group_id)
        messages: list[dict] = result["messages"]

        # 转换成转发节点(TODO forward消息段的解析待优化)
        nodes = []
        for message in messages:
            node = {
                "type": "node",
                "data": {
                    "name": message["sender"]["nickname"],
                    "uin": message["sender"]["user_id"],
                    "content": message["message"],
                },
            }
            nodes.append(node)

        # 发送
        if self.manage_group:
            await client.send_group_forward_msg(
                group_id=int(self.manage_group), messages=nodes
            )
        elif self.admins_id:
            for admin_id in self.admins_id:
                if admin_id.isdigit():
                    await client.send_private_forward_msg(
                        user_id=int(admin_id), messages=nodes
                    )
    @filter.permission_type(filter.PermissionType.ADMIN)
    @filter.command("抽查")
    async def check_messages_handle(
        self, event: AiocqhttpMessageEvent, target_group_id: int
    ):
        """
        抽查指定群聊的消息
        """
        try:
            await self.check_messages(
                client=event.bot,
                target_group_id=target_group_id,
            )
            event.stop_event()
        except Exception as e:
            logger.exception(e)
            yield event.plain_result(f"抽查群({target_group_id})消息失败: {e}")

