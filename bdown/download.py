"""
Created on 2025-05-05

@author: wf
"""
from tqdm import tqdm
import hashlib
import os
from dataclasses import field
from typing import List, Tuple

import requests
from lodstorage.yamlable import lod_storable
from concurrent.futures import ThreadPoolExecutor
from threading import Lock

@lod_storable
class Block:
    """
    A single download block.
    """

    block: int
    path: str
    offset: int
    md5: str = None  # full md5 hash
    md5_head: str = None  # hash of first chunk

    def calc_md5(self, base_path: str, chunk_size: int = 8192, chunk_limit: int = None) -> str:
        """
        Calculate the MD5 checksum of this block's file.

        Args:
            base_path: Directory where the block's relative path is located.
            chunk_size: Bytes per read operation (default: 8192).
            chunk_limit: Maximum number of chunks to read (e.g. 1 for md5_head).

        Returns:
            str: The MD5 hexadecimal digest.
        """
        full_path = os.path.join(base_path, self.path)
        hash_md5 = hashlib.md5()
        index = 0

        with open(full_path, "rb") as f:
            for chunk in iter(lambda: f.read(chunk_size), b""):
                hash_md5.update(chunk)
                index += 1
                if chunk_limit is not None and index >= chunk_limit:
                    break

        return hash_md5.hexdigest()


    @classmethod
    def ofResponse(
        cls,
        block_index: int,
        offset: int,
        chunk_size: int,
        target_path: str,
        response: requests.Response,
        progress_bar=None,
    ) -> "Block":
        """
        Create a Block from a download HTTP response.

        Args:
            block_index: Index of the block.
            offset: Byte offset within the full file.
            target_path: Path to the .part file to write.
            response: The HTTP response streaming the content.
            progress_bar: optional progress_bar for reporting download progress.

        Returns:
            Block: The constructed block with calculated md5.
        """
        hash_md5 = hashlib.md5()
        hash_head = hashlib.md5()
        first = True
        block_path=os.path.basename(target_path)
        if progress_bar:
            progress_bar.set_description(block_path)
        with open(target_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=chunk_size):
                f.write(chunk)
                hash_md5.update(chunk)
                if first:
                    hash_head.update(chunk)
                    first = False
                if progress_bar:
                    progress_bar.update(len(chunk))
        block = cls(
            block=block_index,
            path=block_path,
            offset=offset,
            md5=hash_md5.hexdigest(),
            md5_head=hash_head.hexdigest(),
        )
        return block


@lod_storable
class BlockDownload:
    name: str
    url: str
    blocksize: int
    chunk_size: int = 8192  # size of a response chunk
    size: int = None
    unit: str = "MB"  # KB, MB, or GB
    md5: str = ""
    blocks: List[Block] = field(default_factory=list)

    def __post_init__(self):
        self.unit_multipliers = {
            "KB": 1024,
            "MB": 1024 * 1024,
            "GB": 1024 * 1024 * 1024,
        }
        if self.unit not in self.unit_multipliers:
            raise ValueError(f"Unsupported unit: {self.unit} - must be KB, MB or GB")
        self.lock = Lock()
        self.active_blocks = set()
        self.progress_lock = Lock()

    @property
    def blocksize_bytes(self) -> int:
        return self.blocksize * self.unit_multipliers[self.unit]

    def block_range_str(self) -> str:
        if not self.active_blocks:
            range_str="∅"
        else:
            min_block = min(self.active_blocks)
            max_block = max(self.active_blocks)
            range_str=f"{min_block}" if min_block == max_block else f"{min_block}–{max_block}"
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
        return int(response.headers.get("Content-Length", 0))

    def block_ranges(
        self, from_block: int, to_block: int
    ) -> List[Tuple[int, int, int]]:
        """
        Generate a list of (index, start, end) tuples for the given block range.

        Args:
            from_block: Index of first block.
            to_block: Index of last block (inclusive).

        Returns:
            List of (index, start, end).
        """
        if self.size is None:
            self.size = self._get_remote_file_size()
        result = []
        block_size = self.blocksize_bytes
        for index in range(from_block, to_block + 1):
            start = index * block_size
            end = min(start + block_size - 1, self.size - 1)
            result.append((index, start, end))
        return result

    def compute_total_bytes(
        self, from_block: int, to_block: int=None
    ) -> Tuple[int, int, int]:
        """
        Compute the total number of bytes to download for a block range.

        Args:
            from_block: First block index.
            to_block: Last block index (inclusive), or None for all blocks.

        Returns:
            Tuple of (from_block, to_block, total_bytes).
        """
        if self.size is None:
            self.size = self._get_remote_file_size()
        total_blocks = (self.size + self.blocksize_bytes - 1) // self.blocksize_bytes
        if to_block is None or to_block >= total_blocks:
            to_block = total_blocks - 1

        total_bytes = 0
        for _, start, end in self.block_ranges(from_block, to_block):
            total_bytes += end - start + 1

        return from_block, to_block, total_bytes

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
            total_blocks = (self.size + self.blocksize_bytes - 1) // self.blocksize_bytes
            to_block = total_blocks - 1

        block_specs = self.block_ranges(from_block, to_block)

        if boost == 1:
            for index, start, end in block_specs:
                self._download_block(index, start, end, target, progress_bar)
        else:
            with ThreadPoolExecutor(max_workers=boost) as executor:
                for index, start, end in block_specs:
                    executor.submit(self._download_block, index, start, end, target, progress_bar)


    def update_progress(self,progress_bar,index:int):
        with self.progress_lock:
            if index>0:
                self.active_blocks.add(index)
            else:
                self.active_blocks.remove(-index)
            if progress_bar:
                progress_bar.set_description(f"Blocks {self.block_range_str()}")

    def _download_block(self, index: int, start: int, end: int, target: str, progress_bar):
        part_name = f"{self.name}-{index:04d}.part"
        part_file = os.path.join(target, part_name)

        if index < len(self.blocks):
            existing = self.blocks[index]
            if os.path.exists(part_file) and existing.md5_head:
                actual_head = existing.calc_md5(
                    base_path=target,
                    chunk_size=self.chunk_size,
                    chunk_limit=1
                )
                if actual_head == existing.md5_head:
                    if progress_bar:
                        progress_bar.set_description(part_name)
                        progress_bar.update(end - start + 1)
                    return

        self.update_progress(progress_bar, index+1)
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
            self.save()
        self.update_progress(progress_bar, -(index+1))

    def get_progress_bar(self, from_block: int, to_block: int):
        _, _, total_bytes = self.compute_total_bytes(from_block, to_block)
        progress_bar = tqdm(total=total_bytes, unit="B", unit_scale=True)
        return progress_bar