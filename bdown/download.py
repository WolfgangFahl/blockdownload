"""
Created on 2025-05-05

@author: wf
"""

import os
import subprocess
from concurrent.futures import ThreadPoolExecutor
from threading import Lock

import requests
from lodstorage.yamlable import lod_storable

from bdown.block import Block
from bdown.block_fiddler import BlockFiddler


@lod_storable
class BlockDownload(BlockFiddler):
    url: str = None

    def __post_init__(self):
        """
        specialized @constructor time initialization
        """
        # call the general  @constructor time initialization
        super().__post_init__()
        self.lock = Lock()
        self.active_blocks = set()
        self.progress_lock = Lock()
        if self.size is None:
            self.size = self._get_remote_file_size()

    def download_via_os(self, target_path: str, cmd=None) -> int:
        """
        Download file using operating system command

        Args:
            target_path: Path where the file should be saved
            cmd: Command to execute as list, defaults to wget

        Returns:
            int: Size of the downloaded file in bytes, or -1 if download failed

        Raises:
            subprocess.CalledProcessError: If the command returns a non-zero exit code
        """
        if cmd is None:
            cmd = ["wget", "-O", target_path, self.url]
        subprocess.run(cmd, check=True)

        if os.path.exists(target_path):
            return os.path.getsize(target_path)
        return -1

    def block_range_str(self) -> str:
        if not self.active_blocks:
            range_str = "∅"
        else:
            min_block = min(self.active_blocks)
            max_block = max(self.active_blocks)
            range_str = (
                f"{min_block}" if min_block == max_block else f"{min_block}–{max_block}"
            )
        return range_str

    @classmethod
    def ofYamlPath(cls, yaml_path: str):
        block_download = cls.load_from_yaml_file(yaml_path)
        block_download.yaml_path = yaml_path
        return block_download

    def save(self):
        if hasattr(self, "yaml_path") and self.yaml_path:
            self.save_to_yaml_file(self.yaml_path)

    def _get_remote_file_size(self) -> int:
        response = requests.head(self.url, allow_redirects=True)
        response.raise_for_status()
        file_size = int(response.headers.get("Content-Length", 0))
        return file_size

    def download(
        self,
        target: str,
        from_block: int = 0,
        to_block: int = None,
        boost: int = 1,
        progress_bar=None,
    ):
        """
        Download selected blocks and save them to individual .part files.

        Args:
            target: Directory to store .part files.
            from_block: Index of the first block to download.
            to_block: Index of the last block (inclusive), or None to download until end.
            boost: Number of parallel download threads to use (default: 1 = serial).
            progress_bar: Optional tqdm-compatible progress bar for visual feedback.
        """
        if self.size is None:
            self.size = self._get_remote_file_size()
        os.makedirs(target, exist_ok=True)

        if to_block is None:
            total_blocks = (
                self.size + self.blocksize_bytes - 1
            ) // self.blocksize_bytes
            to_block = total_blocks - 1

        block_specs = self.block_ranges(from_block, to_block)

        if boost == 1:
            for index, start, end in block_specs:
                self._download_block(index, start, end, target, progress_bar)
        else:
            with ThreadPoolExecutor(max_workers=boost) as executor:
                for index, start, end in block_specs:
                    executor.submit(
                        self._download_block, index, start, end, target, progress_bar
                    )

    def update_progress(self, progress_bar, index: int):
        with self.progress_lock:
            if index > 0:
                self.active_blocks.add(index)
            else:
                self.active_blocks.remove(-index)
            if progress_bar:
                progress_bar.set_description(f"Blocks {self.block_range_str()}")

    def _download_block(
        self, index: int, start: int, end: int, target: str, progress_bar
    ):
        part_name = f"{self.name}-{index:04d}.part"
        part_file = os.path.join(target, part_name)

        if index < len(self.blocks):
            existing = self.blocks[index]
            if os.path.exists(part_file) and existing.md5_head:
                actual_head = existing.calc_md5(
                    base_path=target, chunk_size=self.chunk_size, chunk_limit=1
                )
                if actual_head == existing.md5_head:
                    if progress_bar:
                        progress_bar.set_description(part_name)
                        progress_bar.update(end - start + 1)
                    return

        self.update_progress(progress_bar, index + 1)
        headers = {"Range": f"bytes={start}-{end}"}
        response = requests.get(self.url, headers=headers, stream=True)
        if response.status_code not in (200, 206):
            raise Exception(f"HTTP {response.status_code}: {response.text}")

        block = Block.ofResponse(
            block_index=index,
            offset=start,
            chunk_size=self.chunk_size,
            target_path=part_file,
            response=response,
            progress_bar=progress_bar,
        )

        with self.lock:
            if index < len(self.blocks):
                self.blocks[index] = block
            else:
                self.blocks.append(block)
            self.sort_blocks()
            self.save()
        self.update_progress(progress_bar, -(index + 1))
