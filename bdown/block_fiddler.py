"""
Created on 2025-05-06

@author: wf
"""
from bdown.block import Block
from typing import List, Tuple
from dataclasses import dataclass,field
from tqdm import tqdm

@dataclass
class BlockFiddler:
    """Base class for block operations with shared functionality"""
    name: str
    blocksize: int
    size: int = None
    unit: str = "MB"  # KB, MB, or GB
    chunk_size: int = 8192  # size of a response chunk
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

    @property
    def blocksize_bytes(self) -> int:
        blocksize_bytes=self.blocksize * self.unit_multipliers[self.unit]
        return blocksize_bytes

    def calculate_block_ranges(self, from_block: int, to_block: int = None) -> List[Tuple[int, int, int]]:
        """
        Calculate block ranges for local files

        Args:
            from_block: First block index
            to_block: Last block index (inclusive), or None for all blocks

        Returns:
            List of (index, start, end) tuples
        """
        if self.size is None:
            raise ValueError("File size must be set before calculating block ranges")

        total_blocks = (self.size + self.blocksize_bytes - 1) // self.blocksize_bytes
        if to_block is None or to_block >= total_blocks:
            to_block = total_blocks - 1

        result = []
        block_size = self.blocksize_bytes
        for index in range(from_block, to_block + 1):
            start = index * block_size
            end = min(start + block_size - 1, self.size - 1)
            result.append((index, start, end))
        return result

    def get_progress_bar(self, from_block: int, to_block: int):
        """Create a progress bar for block operations"""
        if to_block is None:
            total_blocks = (self.size + self.blocksize_bytes - 1) // self.blocksize_bytes
            to_block = total_blocks - 1

        total_bytes = 0
        for _, start, end in self.calculate_block_ranges(from_block, to_block):
            total_bytes += end - start + 1

        progress_bar = tqdm(total=total_bytes, unit="B", unit_scale=True)
        # Set a default description and force an immediate update
        progress_bar.set_description(f"Processing {self.name}")
        progress_bar.update(0)
        return progress_bar