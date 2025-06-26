import asyncio
import aiohttp
import re
import os
import aiofiles

def clean_cookie(cookie):
    # 使用正则表达式移除无法编码的字符
    return re.sub(r'[^\x00-\x7F]+', '', cookie)

async def get_location_from_url(url):
    """
    处理单个 URL，获取响应头中的 location，并模拟指定的请求头。

    Args:
        url: 单个 URL。

    Returns:
        包含 URL 和 location 的字典。
    """
    headers = {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Encoding": "gzip, deflate, br, zstd",
        "Accept-Language": "zh-CN,zh;q=0.8,zh-TW;q=0.7,zh-HK;q=0.5,en-US;q=0.3,en;q=0.2",
        "Connection": "keep-alive",
        "Cookie": clean_cookie("ttwid=1%7CPZUWvh1QolM1egtvlbS98EnKH_sKJX4ncAj4c7NljNc%7C1739777124%7C3eae520005da7580059986002ed00ebfff8e9c408cbf9236573064d0397e379d; UIFID_TEMP=613634dc34f23bc54c4e69bde1e8beb81fe7a3637c44b96e832cc4e593748ae48b6163ddb8aa3c395b86dcf54503f25fbac02747e661a44cfe125efe21c6341047f267a096e947a590131d41892f55b6; fpk1=U2FsdGVkX1+jfgReUUml29d9icaBSGsvVqJ/Wm3HoiE3cuub8fh+ky6uvAUCdEHN377qKLNPr3JZ3PuGCsTu8A==; fpk2=4c9c7df88604dc1a888a18bba9790140; UIFID=613634dc34f23bc54c4e69bde1e8beb81fe7a3637c44b96e832cc4e593748ae4…n1jlrvkoILhMZQTTLRC4P6z4xLZ8fUM%2F1741881600000%2F0%2F1741857606242%2F0%22; download_guide=%223%2F20250312%2F0%22; __ac_signature=_02B4Z6wo00f015HPVnQAAIDD3O5v3hEaPYOR.lLAAIOpe3; bd_ticket_guard_client_data=eyJiZC10aWNrZXQtZ3VhcmQtdmVyc2lvbiI6MiwiYmQtdGlja2V0LWd1YXJkLWl0ZXJhdGlvbi12ZXJzaW9uIjoxLCJiZC10aWNrZXQtZ3VhcmQtcmVlLXB1YmxpYy1rZXkiOiJCRzJ6YlVCZVBKbVRCb1VUK2J4bEVqTMNSQ0xESWF3OUpTemlzemJ4NUovRlFJM0ZacWtMK20rUGhOZXZZaDFnR2RtVjJTdFdqYk8xL2VMVlh1NXVPa0E9IiwiYmQtdGlja2V0LWd1YXJkLXdlYi12ZXJzaW9uIjoyfQ%3D%3D"),
        "Host": "www.douyin.com",
        "Priority": "u=0, i",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "TE": "trailers",
        "Upgrade-Insecure-Requests": "1",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:136.0) Gecko/20100101 Firefox/136.0"
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, allow_redirects=False) as response:
                if response.status == 302 or response.status == 301:
                    location = response.headers.get('location')
                    return {'url': url, 'location': location}
                else:
                    return {'url': url, 'location': None, 'status_code': response.status}
    except aiohttp.ClientError as e:
        return {'url': url, 'error': str(e)}

async def download_video(url, filename="video.mp4"):
    """
    Downloads a video from the given URL asynchronously.

    Args:
        url (str): The URL of the video.
        filename (str): The filename to save the video as.
    """
    # Check if the file already exists
    if os.path.exists(filename):
        print(f"File '{filename}' already exists. Skipping download.")
        return

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:136.0) Gecko/20100101 Firefox/136.0'
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as response:
                response.raise_for_status()

                if response.status == 304:
                    print("Video not modified. No download needed.")
                    return

                os.makedirs(os.path.dirname(filename), exist_ok=True)

                total_size = int(response.headers.get('content-length', 0))
                block_size = 1024

                async with aiofiles.open(filename, 'wb') as file:
                    downloaded = 0
                    async for data in response.content.iter_chunked(block_size):
                        await file.write(data)
                        downloaded += len(data)
                        if total_size:
                            print(f"\rDownloaded: {downloaded / total_size * 100:.2f}%", end="")
                if total_size:
                    print("\nDownload complete!")
                else:
                    print("Download complete. Content-Length header missing, progress not shown.")

    except aiohttp.ClientError as e:
        print(f"Error downloading video: {e}")
    except IOError as e:
        print(f"Error writing file: {e}")

async def download(url, filename="video.mp4"):
    """
    Downloads videos from the given list of URLs asynchronously.

    Args:
        urls (list): A list of URLs of the videos.
        filename (str): The base filename to save the videos as.
    """
    location_data = await get_location_from_url(url)

    if location_data and location_data.get('location'):
        download_url = location_data.get('location')
        await download_video(download_url, filename)
    else:
        await download_video(url, filename)
        # print(f"Error getting location for {url}")


# if __name__ == "__main__":
#     url = "https://p3-pc-sign.douyinpic.com/tos-cn-i-0813c000-ce/oMAnCVBQBAEwiiwI8Td2SMAIJPQY0hADhiAPZ~tplv-dy-aweme-images:q75.jpeg?lk3s=138a59ce&x-expires=1744963200&x-signature=Cgf9pS1Fne0tvRujCHt6htkHP%2BI%3D&from=327834062&s=PackSourceEnum_AWEME_DETAIL&se=false&sc=image&biz_tag=aweme_images&l=202503191654145A604C96898653070E42"
#     asyncio.run(download(url))