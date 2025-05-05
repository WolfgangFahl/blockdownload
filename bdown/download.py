"""
Created on 2025-05-05

@author: wf
"""

import hashlib
import os
from dataclasses import field
from typing import List, Tuple

import requests
from lodstorage.yamlable import lod_storable


@lod_storable
class Block:
    """
    A single download block.
    """
    block: int
    path: str
    offset: int
    md5: str = None

    def calc_md5(self, base_path: str) -> str:
        """
        Calculate the MD5 checksum of this block's file.

        Args:
            base_path: The directory in which the block's relative path is located.

        Returns:
            str: The MD5 hexadecimal digest of the block file.
        """
        full_path = os.path.join(base_path, self.path)
        hash_md5 = hashlib.md5()
        with open(full_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                hash_md5.update(chunk)
        md5 = hash_md5.hexdigest()
        return md5

    @classmethod
    def ofResponse(cls, block_index: int, offset: int, target_path: str,
                   response: requests.Response, progress=None) -> "Block":
        """
        Create a Block from a download HTTP response.

        Args:
            block_index: Index of the block.
            offset: Byte offset within the full file.
            target_path: Path to the .part file to write.
            response: The HTTP response streaming the content.
            progress: Optional callable(chunk_size: int) for reporting download progress.

        Returns:
            Block: The constructed block with calculated md5.
        """
        hash_md5 = hashlib.md5()
        with open(target_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
                hash_md5.update(chunk)
                if progress:
                    progress(len(chunk))
        return cls(
            block=block_index,
            path=os.path.basename(target_path),
            offset=offset,
            md5=hash_md5.hexdigest()
        )


@lod_storable
class BlockDownload:
    url: str
    blocksize: int
    size: int = None
    size_bytes: int = None
    unit: str = "MB"  # KB, MB, or GB
    md5: str = None
    blocks: List[Block] = field(default_factory=list)

    def __post_init__(self):
        self.unit_multipliers = {
            "KB": 1024,
            "MB": 1024 * 1024,
            "GB": 1024 * 1024 * 1024,
        }
        if self.unit not in self.unit_multipliers:
            raise ValueError(f"Unsupported unit: {self.unit} - must be KB, MB or GB")

    @property
    def blocksize_bytes(self) -> int:
        return self.blocksize * self.unit_multipliers[self.unit]

    @classmethod
    def ofYamlPath(cls,yaml_path:str):
        block_download=cls.load_from_yaml_file(yaml_path)
        block_download.yaml_path=yaml_path
        return block_download

    def save(self):
        if hasattr(self, "yaml_path") and self.yaml_path:
            self.save_to_yaml_file(self.yaml_path)

    def _get_remote_file_size(self) -> int:
        response = requests.head(self.url, allow_redirects=True)
        response.raise_for_status()
        return int(response.headers.get("Content-Length", 0))

    def block_ranges(self, from_block: int, to_block: int) -> List[Tuple[int, int, int]]:
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

    def compute_total_bytes(self, from_block: int, to_block: int = None) -> Tuple[int, int, int]:
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

    def download(self, target: str, from_block: int = 0, to_block: int = None, yaml_path:str=None,progress=None):
        """
        Download selected blocks and save them to individual .part files.

        Args:
            target: Directory to store part files.
            from_block: First block index.
            to_block: Last block index (inclusive), or None to download all.
            progress: Optional callable(chunk_size: int) to track progress.
        """
        if self.size is None:
            self.size = self._get_remote_file_size()
        os.makedirs(target, exist_ok=True)
        self.blocks.clear()

        if to_block is None:
            total_blocks = (self.size + self.blocksize_bytes - 1) // self.blocksize_bytes
            to_block = total_blocks - 1

        for index, start, end in self.block_ranges(from_block, to_block):
            part_file = os.path.join(target, f"{index:04d}.part")
            headers = {"Range": f"bytes={start}-{end}"}
            response = requests.get(self.url, headers=headers, stream=True)
            if response.status_code not in (200, 206):
                raise Exception(f"HTTP {response.status_code}: {response.text}")
            block = Block.ofResponse(index, start, part_file, response, progress=progress)
            self.blocks.append(block)
            self.save()
