import json
import mimetypes
import os
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import aiofiles
import aiohttp

from astrbot.api import logger
from astrbot.core.platform import AstrMessageEvent


def get_mime_type(file_path):
    mime_type, _ = mimetypes.guess_type(file_path)
    return mime_type or "application/octet-stream"


def get_file_size(file_path):
    return os.path.getsize(file_path)


class CloudreveHandler:

    def __init__(self, host, username=None, password=None, cloud_upload_folder_path=None):
        self.host = host
        self.timezone = ZoneInfo("Asia/Shanghai")
        self.access_expires = datetime.now(self.timezone)
        self.refresh_expires = datetime.now(self.timezone)
        self.access_token = None
        self.refresh_token = None
        self.username = username
        self.password = password
        self.cloud_upload_folder_path = cloud_upload_folder_path
        self.storage_policy = None

    async def call_login_token(self, event: AstrMessageEvent = None):
        if self.refresh_expires <= datetime.now(self.timezone):
            await self.login(event)
            await self.refresh_storage_policy(event)
        elif self.access_expires <= datetime.now(self.timezone):
            await self.call_refresh_token(event)
            await self.refresh_storage_policy(event)


    async def call_refresh_token(self, event: AstrMessageEvent = None):
        if not self.refresh_expires < datetime.now(self.timezone):
            return
        data = {
            "refresh_token": self.refresh_token,
        }
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                        url=f"{self.host}/api/v4/session/token/refresh",
                        json=data,
                ) as response:
                    if response.status != 200:
                        logger.error(f"调用 刷新 token 失败: {await response.text()}")
                        await event.plain_result(
                            "刷新 token 失败，请检查配置或网络连接。"
                        )
                    if response.status == 200:
                        logger.info(f"调用 刷新 token 成功: {await response.text()}")
                        response_data = await response.json()
                        if "data" in response_data:
                            token = response_data["data"]
                            self.access_token = token.get("access_token")
                            self.refresh_token = token.get("refresh_token")
                            self.access_expires =datetime.fromisoformat(token.get("access_expires"))
                            self.refresh_expires = datetime.fromisoformat(token.get("refresh_expires"))
        except Exception as e:
            logger.error(f"刷新 token 时发生错误: {e}")
            event.plain_result(f"刷新 token 失败: {str(e)}")

    async def login(self, event: AstrMessageEvent = None):
        data = {
            "captcha": None,
            "ticket": None,
            "email": self.username,
            "password": self.password
        }
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                        url=f"{self.host}/api/v4/session/token",
                        json=data,
                ) as response:
                    if response.status != 200:
                        logger.error(f"调用 登录 失败: {await response.text()}")
                        event.plain_result(
                            f"调用cloudreve 登录 失败: {await response.text()}"
                        )
                    if response.status == 200:
                        logger.info(f"调用 登录 成功: {await response.text()}")
                        response_data = await response.json()
                        if "data" in response_data:
                            result = response_data["data"]
                            token = result.get("token", {})
                            self.access_token = token.get("access_token")
                            self.refresh_token = token.get("refresh_token")
                            self.access_expires =datetime.fromisoformat(token.get("access_expires"))
                            self.refresh_expires = datetime.fromisoformat(token.get("refresh_expires"))
        except Exception as e:
            logger.error(f"上传文件时发生错误: {e}")
            event.plain_result(f"上传文件失败: {str(e)}")

    async def upload_files(self, file_paths:list[str], type: str, event: AstrMessageEvent):
        file_name = os.path.basename(file_paths[0])
        file_name_without_ext, _ = os.path.splitext(file_name)
        folder_uri = f"cloudreve://my/{self.cloud_upload_folder_path}/{type}/{file_name_without_ext}"
        await self.create_folder(folder_uri, event)
        uris = []
        for file_path in file_paths:
            file_name = os.path.basename(file_path)
            uri = f"{folder_uri}/{file_name}"
            sessionId, chunkSize, exists = await self.create_upload_file_session(file_name, uri, file_path, event)
            if exists:
                logger.warning(f"文件 {file_name} 已存在，跳过上传。")
                uris.append(uri)
                continue
            await self._upload_file_(sessionId, chunkSize, file_path, event)
            await self.close_upload_file_session(sessionId, uri, event)
            uris.append(uri)
        return uris


    async def upload_file(self, file_path, type: str, event: AstrMessageEvent):

        """上传文件到 Cloudreve"""
        file_name = os.path.basename(file_path)
        folder_uri = f"cloudreve://my/{self.cloud_upload_folder_path}/{type}"
        uri = f"{folder_uri}/{file_name}"
        await self.create_folder(folder_uri, event)
        sessionId, chunkSize, exists = await self.create_upload_file_session(file_name, uri, file_path, event)
        if exists:
            logger.warning(f"文件 {file_name} 已存在，跳过上传。")
            return file_name, file_path, uri
        await self._upload_file_(sessionId, chunkSize, file_path, event)
        await self.close_upload_file_session(sessionId, uri, event)
        return uri

    async def upload_files_and_get_file_direct_url(self, file_paths: list[str] , type: str, event: AstrMessageEvent):
        logger.info(f"开始上传 文件: {file_paths} 到 Cloudreve, 类型: {type}")
        uris = await self.upload_files(file_paths, type, event)
        logger.info(f"上传文件完成, 返回的 URIs: {uris}, 准备获取直链")
        links = await self.get_files_direct_url(uris, event)
        logger.info(f"获取直链完成, 返回的直链: {links}")
        if links:
            return links
        else:
            logger.error("获取文件直链失败")
            event.plain_result("获取文件直链失败，请检查配置或网络连接。")
            return None

    async def upload_file_and_get_file_direct_url(self, file_path, type, event: AstrMessageEvent):
        uri = await self.upload_file(file_path, type, event)
        links = await self.get_files_direct_url([uri], event)
        if links:
            return links[0]
        else:
            logger.error("获取文件直链失败")
            event.plain_result("获取文件直链失败，请检查配置或网络连接。")
            return None

    async def create_upload_file_session(self, file_name, uri, file_path, event: AstrMessageEvent):
        await self.before_request(event)
        """创建上传文件会话"""
        if not os.path.exists(file_path):
            logger.error(f"文件 {file_path} 不存在")
            event.plain_result("文件不存在，请检查路径是否正确。")
            return None, None, None
        data = {
            "uri": uri,
            "size": get_file_size(file_path),
            "policy_id": self.storage_policy,
            "last_modified": int(datetime.now().timestamp()),
            "mime_type": get_mime_type(file_name),
        }
        headers = {
            "Authorization": f"Bearer {self.access_token}" if self.access_token else None,
            "Content-Type": "application/json",
        }
        try:
            async with aiohttp.ClientSession() as session:
                async with session.put(
                        url=f"{self.host}/api/v4/file/upload",
                        headers=headers,
                        json=data,
                ) as response:
                    if response.status != 200:
                        logger.error(f"调用 开启上传 文件失败: {await response.text()}")
                        event.plain_result(
                            "上传文件失败，请检查配置或网络连接。"
                        )
                        return None, None, None

                    logger.info(f"调用 开启上传 文件成功: {await response.text()}")
                    response_data = await response.json()

                    if "data" in response_data:
                        result = response_data["data"]
                        sessionId = result.get("session_id", "")
                        chunkSize = result.get("chunk_size", 1024 * 1024)  # 默认1MB
                        if not sessionId:
                            logger.warning("n8n 开启上传 返回结果中没有 'session_id' 字段")
                            event.plain_result(
                                "n8n 开启上传 调用成功,响应缺少session_id字段,请检查配置或联系管理员"
                            )
                            return None, None, None
                        else:
                            return sessionId, chunkSize, False
                    elif response_data.get("code") == 40004:
                        return None, None, True

        except Exception as e:
            logger.error(f"上传文件时发生错误: {e}")
            event.plain_result(f"上传文件失败: {str(e)}")
        return None, None

    async def _upload_file_(self, session_id, chunk_size, file_path, event: AstrMessageEvent):
        await self.before_request(event)
        """上传文件到 Cloudreve"""
        headers = {
            "Authorization": f"Bearer {self.access_token}" if self.access_token else None,
            "Content-Type": "application/octet-stream",
        }
        async with aiofiles.open(file_path, 'rb') as file:
            index = 0
            async with aiohttp.ClientSession() as session:
                while chunk := await file.read(chunk_size):  # Read in chunks
                    async with session.post(
                            url=f"{self.host}/api/v4/file/upload/{session_id}/{index}",
                            headers=headers,
                            data=chunk
                    ) as upload_response:
                        if upload_response.status != 200:
                            logger.error(f"文件上传失败: {await upload_response.text()}")
                            event.plain_result(
                                "文件上传失败，请检查配置或网络连接。"
                            )
                            return
                        logger.info(f"文件上传成功: {await upload_response.text()}")
                        index += 1

    async def close_upload_file_session(self, session_id, uri, event: AstrMessageEvent):
        await self.before_request(event)
        """关闭上传文件会话"""
        headers = {
            "Authorization": f"Bearer {self.access_token}" if self.access_token else None,
            "Content-Type": "application/json",
        }
        try:
            async with aiohttp.ClientSession() as session:
                async with session.delete(
                        url=f"{self.host}/api/v4/file/upload",
                        headers=headers,
                        json={"id": session_id, "uri": uri}
                ) as response:
                    if response.status != 200:
                        logger.error(f"调用 关闭上传 文件失败: {await response.text()}")
                        event.plain_result(
                            "关闭上传失败，请检查配置或网络连接。"
                        )
                        return

                    logger.info(f"调用 关闭上传 文件成功: {await response.text()}")
        except Exception as e:
            logger.error(f"关闭上传会话时发生错误: {e}")
            event.plain_result(f"关闭上传会话失败: {str(e)}")

    async def get_files_direct_url(self, uris, event):
        await self.before_request(event)
        """获取文件直链"""
        headers = {
            "Authorization": f"Bearer {self.access_token}" if self.access_token else None,
            "Content-Type": "application/json",
        }
        try:
            async with aiohttp.ClientSession() as session:
                async with session.put(
                        url=f"{self.host}/api/v4/file/source",
                        headers=headers,
                        json={"uris": uris}
                ) as response_data:
                    if response_data.status != 200:
                        logger.error(f"调用 获取直链 失败: {await response_data.text()}")
                        await event.plain_result(
                            "获取直链失败，请检查配置或网络连接。"
                        )
                        return None
                    response_json = await response_data.json()
                    # logger.info(f"获取直链 成功 : {response_data.text()}")
                    if "data" in response_json:
                        results = response_json["data"]
                        if results and len(results) > 0:
                            direct_urls = []
                            for result in results:
                                if "link" in result:
                                    direct_urls.append(result["link"])
                            if direct_urls:
                                logger.info(f"获取直链 成功: {direct_urls}")
                                event.plain_result(f"获取直链成功: {direct_urls}")
                                return direct_urls
                            else:
                                logger.warning("获取直链返回结果中没有 'direct_url' 字段")
                                event.plain_result(
                                    "获取直链调用成功,响应缺少direct_url字段,请检查配置或联系管理员"
                                )
        except Exception as e:
            logger.error(f"获取直链时发生错误: {e}")
            await event.plain_result(f"获取直链失败: {str(e)}")
        return None

    async def create_folder(self, folder_uri, event):
        await self.before_request(event)
        data = {
            "type": "folder",
            "uri": folder_uri,
            "err_on_conflict": False
        }
        headers = {
            "Authorization": f"Bearer {self.access_token}" if self.access_token else None,
            "Content-Type": "application/json",
        }
        try:
            logger.info(f"调用 创建文件夹 {folder_uri} : {json.dumps(data)}")

            async with aiohttp.ClientSession() as session:
                async with session.post(
                        url=f"{self.host}/api/v4/file/create",
                        headers=headers,
                        json=data,
                ) as response:
                    if response.status != 200:
                        logger.error(f"调用 创建文件夹 失败: {await response.text()}")
                        event.plain_result(
                            "创建文件夹 失败，请检查配置或网络连接。"
                        )
                    logger.info(f"调用 创建文件夹 {folder_uri} 成功: {await response.text()}")
        except Exception as e:
            logger.error(f"创建文件夹时发生 错误: {e}")
            event.plain_result(f"创建文件夹 失败: {str(e)}")
        return None, None

    async def before_request(self, event):
        await self.call_login_token(event)

    async def refresh_storage_policy(self, event):
        """获取文件存储策略,注意这里不用调用登录接口,因为此方法会在登录时自动调用"""
        headers = {
            "Authorization": f"Bearer {self.access_token}" if self.access_token else None,
            "Content-Type": "application/json",
        }
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                        url=f"{self.host}/api/v4/file",
                        headers=headers,
                        params={"uri": "cloudreve://my"}
                ) as response_data:
                    if response_data.status != 200:
                        logger.error(f"调用 获取文件策略 失败: {await response_data.text()}")
                        await event.plain_result(
                            f"获取文件策略 失败，请检查配置或网络连接: {await response_data.text()}"
                        )
                        return None
                    response_json = await response_data.json()
                    if "data" in response_json:
                        data = response_json["data"]
                        if data and  "storage_policy" in data:
                            self.storage_policy = data["storage_policy"]['id']
                        else:
                            await event.plain_result(
                                "获取文件策略 成功, 响应缺少 storage_policy 字段,请检查配置或联系管理员"
                            )
                    else:
                        await event.plain_result(
                            "获取文件策略 成功, 响应缺少 data 字段,请检查配置或联系管理员"
                        )
        except Exception as e:
            logger.error(f"获取文件策略 发生错误: {e}")
            await event.plain_result(f"获取文件策略 失败: {str(e)}")
        return None

