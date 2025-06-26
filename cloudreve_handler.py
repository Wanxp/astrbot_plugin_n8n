import mimetypes
import os
from datetime import datetime

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
        self.access_expires = datetime.now()
        self.refresh_expires = datetime.now()
        self.access_token = None
        self.refresh_token = None
        self.username = username
        self.password = password
        self.cloud_upload_folder_path = cloud_upload_folder_path



    async def login_token(self, event: AstrMessageEvent = None):
        if self.refresh_expires <= datetime.now():
            await self.login(event)
        elif self.access_expires <= datetime.now():
            await self.refresh_token(event)


    async def refresh_token(self, event: AstrMessageEvent = None):
        if not self.refresh_expires < datetime.now():
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
                            self.access_expires = datetime.strptime(token.get("access_expires"))
                            self.refresh_expires = datetime.strptime(token.get("refresh_expires"))
        except Exception as e:
            logger.error(f"刷新 token 时发生错误: {e}")
            await event.plain_result(f"刷新 token 失败: {str(e)}")

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
                        await event.plain_result(
                            "登录失败，请检查配置或网络连接。"
                        )
                    if response.status == 200:
                        logger.info(f"调用 登录 成功: {await response.text()}")
                        response_data = await response.json()
                        if "data" in response_data:
                            result = response_data["data"]
                            token = result.get("token", {})
                            self.access_token = token.get("access_token")
                            self.refresh_token = token.get("refresh_token")
                            self.access_expires = datetime.strptime(token.get("access_expires"))
                            self.refresh_expires = datetime.strptime(token.get("refresh_expires"))
         except Exception as e:
                logger.error(f"上传文件时发生错误: {e}")
                yield event.plain_result(f"上传文件失败: {str(e)}")

    async def upload_files(self, file_paths:list[str], type: str, event: AstrMessageEvent):
        file_name = os.path.basename(file_paths[0])
        file_name_without_ext, _ = os.path.splitext(file_name)
        folder_uri = f"cloudreve://{self.cloud_upload_folder_path}/{type}/{file_name_without_ext}"
        await self.create_folder(folder_uri, event)
        uris = []
        for file_path in file_paths:
            file_name = os.path.basename(file_path)
            uri = f"{folder_uri}/{file_name}"
            sessionId, chunkSize = await self.create_upload_file_session(file_name, uri, file_path, event)
            await self._upload_file_(sessionId, chunkSize, file_path, event)
            await self.close_upload_file_session(sessionId, uri, event)
            uris.append(uri)
        return uris


    async def upload_file(self, file_path, type: str, event: AstrMessageEvent):
        """上传文件到 Cloudreve"""
        file_name = os.path.basename(file_path)
        folder_uri = f"cloudreve://{self.cloud_upload_folder_path}/{type}"
        uri = f"{folder_uri}/{file_name}"
        await self.create_folder(folder_uri, event)
        sessionId, chunkSize = await self.create_upload_file_session(file_name, uri, file_path, event)
        await self._upload_file_(sessionId, chunkSize, file_path, event)
        await self.close_upload_file_session(sessionId, uri, event)
        return file_name, file_path, uri

    async def upload_files_and_get_file_direct_url(self, file_path, type, event: AstrMessageEvent):
        file_name, file_path, uri = await self.upload_file(file_path, type, event)
        links = await self.get_files_direct_url([uri], event)
        if links:
            return links
        else:
            logger.error("获取文件直链失败")
            await event.plain_result("获取文件直链失败，请检查配置或网络连接。")
            return None

    async def create_upload_file_session(self, file_name, uri, file_path, event: AstrMessageEvent):
        """创建上传文件会话"""
        if not os.path.exists(file_path):
            logger.error(f"文件 {file_path} 不存在")
            await event.plain_result("文件不存在，请检查路径是否正确。")
            return None, None
        data = {
            "uri": uri,
            "size": get_file_size(file_path),
            "policy_id": "1",
            "last_modified": datetime.now().timestamp(),
            "mime_type": get_mime_type(file_name),
        }
        headers = {
            "Authorization": f"Bearer {self.access_token}" if self.access_token else None,
            "Content-Type": "application/json",
        }
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                        url=f"{self.host}/api/v4/file/upload",
                        headers=headers,
                        json=data,
                ) as response:
                    if response.status != 200:
                        logger.error(f"调用 开启上传 文件失败: {await response.text()}")
                        await event.plain_result(
                            "上传文件失败，请检查配置或网络连接。"
                        )
                        return None, None

                    logger.info(f"调用 开启上传 文件成功: {await response.text()}")
                    response_data = await response.json()

                    if "data" in response_data:
                        result = response_data["data"]
                        sessionId = result.get("session_id", "")
                        chunkSize = result.get("chunk_size", 1024 * 1024)  # 默认1MB
                        if not sessionId:
                            logger.warning("n8n 开启上传 返回结果中没有 'session_id' 字段")
                            await event.plain_result(
                                "n8n 开启上传 调用成功,响应缺少session_id字段,请检查配置或联系管理员"
                            )
                        else:
                            return sessionId, chunkSize
        except Exception as e:
            logger.error(f"上传文件时发生错误: {e}")
            await event.plain_result(f"上传文件失败: {str(e)}")
        return None, None

    async def _upload_file_(self, session_id, chunk_size, file_path, event: AstrMessageEvent):
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
                            await event.plain_result(
                                "文件上传失败，请检查配置或网络连接。"
                            )
                            return
                        logger.info(f"文件上传成功: {await upload_response.text()}")
                        index += 1

    async def close_upload_file_session(self, session_id, uri, event: AstrMessageEvent):
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
                        await event.plain_result(
                            "关闭上传失败，请检查配置或网络连接。"
                        )
                        return

                    logger.info(f"调用 关闭上传 文件成功: {await response.text()}")
        except Exception as e:
            logger.error(f"关闭上传会话时发生错误: {e}")
            await event.plain_result(f"关闭上传会话失败: {str(e)}")

    async def get_files_direct_url(self, uris, event):
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
                    if "data" in response_json:
                        results = response_json["data"]
                        if results and len(results) > 0:
                            direct_urls = []
                            for result in results:
                                if "link" in result:
                                    direct_urls.append(result["link"])
                            if direct_urls:
                                logger.info(f"获取直链成功: {direct_urls}")
                                await event.plain_result(f"获取直链成功: {direct_urls}")
                                return direct_urls
                            else:
                                logger.warning("获取直链返回结果中没有 'direct_url' 字段")
                                await event.plain_result(
                                    "获取直链调用成功,响应缺少direct_url字段,请检查配置或联系管理员"
                                )
        except Exception as e:
            logger.error(f"获取直链时发生错误: {e}")
            await event.plain_result(f"获取直链失败: {str(e)}")
        return None

    async def create_folder(self, folder_uri, event):
        data = {
            "type": "folder",
            "uri": folder_uri,
            "err_on_conflict": True
        }
        headers = {
            "Authorization": f"Bearer {self.access_token}" if self.access_token else None,
            "Content-Type": "application/json",
        }
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                        url=f"{self.host}/api/v4/file/create",
                        headers=headers,
                        json=data,
                ) as response:
                    if response.status != 200:
                        logger.error(f"调用 创建文件夹 失败: {await response.text()}")
                        await event.plain_result(
                            "创建文件夹 失败，请检查配置或网络连接。"
                        )
                    logger.info(f"调用 创建文件夹 成功: {await response.text()}")
        except Exception as e:
            logger.error(f"创建文件夹时发生 错误: {e}")
            await event.plain_result(f"创建文件夹 失败: {str(e)}")
        return None, None

