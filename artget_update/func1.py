import time
from pathlib import Path
from typing import Union

import requests
from rich.progress import (
    BarColumn,
    DownloadColumn,
    Progress,
    TaskID,
    TextColumn,
    TimeRemainingColumn,
    TransferSpeedColumn,
)


class DownloadFileWithChuck:
    def __init__(self, url: str, chuck_size: int, save_filename: Union[str, Path]):
        self.url = url
        self.save_file = save_filename
        self.chuck_size = chuck_size
        self.file_size = 0
        self.write_chuck = 1024 * 1024
        self.ranges = []
        self.task_start = False
        self.progress = Progress(
            TextColumn("[bold blue]{task.fields[filename]}", justify="right"),
            BarColumn(bar_width=None),
            "[progress.percentage]{task.percentage:>3.1f}%",
            "•",
            DownloadColumn(),
            "•",
            TransferSpeedColumn(),
            "•",
            TimeRemainingColumn(),
        )
        self.task_id: TaskID = None
        self.init_downloader()

    def init_downloader(self):
        self.get_download_file_size()
        self.get_file_chuck()
        self.init_file()
        self.init_progress()

    def init_progress(self):
        self.task_id: TaskID = self.progress.add_task(
            f"{self.save_file}下载ing...", filename=self.save_file, start=False, total=self.file_size
        )
        self.progress.start_task(self.task_id)

    def init_file(self):
        """
        初始化文件,分片下载需要文件先存在
        """
        with open(self.save_file, "wb") as f:
            pass

    def get_download_file_size(self):
        """
        获取待下载的文件的大小,需要服务实现head接口
        """
        response = requests.head(self.url)
        file_size = int(response.headers.get("content-length"))
        self.file_size = file_size

    def get_file_chuck(self):
        """
        根据切片大小获取文件下载的分片情况
        arg file_size: 文件大小,单位Bit
        arg chuck_size: 整个文件切片数
        return: eg: [(0,100), (101, 200)]
        """
        range_size = self.file_size // self.chuck_size
        ranges = [(i * range_size, (i + 1) * range_size - 1) for i in range(self.chuck_size)]
        ranges[-1] = (ranges[-1][0], self.file_size - 1)
        self.ranges = ranges

    def download_file_with_chuck(self, start: int, end: int):
        """
        根据切片下载文件
        arg: start:文件开始的下载字节数
        arg: end:文件结束下载的字节数
        """
        # 这里的headers的key需要和服务端设定的保持一直,fastapi中_和-会互相转换,但是必须写-
        headers = {"range-header": f"bytes={start}-{end}"}
        # 流式写入
        response = requests.get(self.url, headers=headers, stream=True)
        with open(self.save_file, "rb+") as file:
            file.seek(start)
            for data in response.iter_content(self.chuck_size):
                file.write(data)
                self.progress.update(self.task_id, advance=self.chuck_size)

    def start_download_file(self):
        from concurrent.futures import ThreadPoolExecutor
        start_time = time.time()
        pool = ThreadPoolExecutor()
        with self.progress:
            for start, end in self.ranges:
                pool.submit(self.download_file_with_chuck, start, end)
        # download_size = 0
        # while download_size < self.file_size:
        #     download_size = Path(self.save_file).stat().st_size
        #     print(f"文件总大小:{self.file_size},当前已经下载:{download_size},剩余:{self.file_size - download_size}")
        end_time = time.time()
        print(f"文件下载用时:{end_time - start_time}")


if __name__ == '__main__':
    download = DownloadFileWithChuck(
        url="http://127.0.0.1:5555/api/v1/user/download/file/streaming", chuck_size=10, save_filename="Download.zip"
    )
    download.start_download_file()
