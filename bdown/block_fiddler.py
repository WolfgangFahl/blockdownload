"""
Created on 2025-05-06

@author: wf
"""
from bdown.block import Block
from typing import List
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

    @property
    def total_blocks(self) -> int:
        if self.size is None:
            raise ValueError("total file size must be set")
        total_blocks=(self.size + self.blocksize_bytes - 1) // self.blocksize_bytes
        return total_blocks

    @property
    def last_block_size(self) -> int:
        total_blocks=self.total_blocks
        if total_blocks == 0:
            last_block_size=0
        else:
            same_size_total=(total_blocks - 1) * self.blocksize_bytes
            last_block_size=self.size -same_size_total
        return last_block_size

    def format_size(self, size_bytes, unit=None, decimals=2, show_unit:bool=True):
        """
        Format byte size to appropriate units

        Args:
            size_bytes: Size in bytes to format
            unit: Target unit (KB, MB, GB) - defaults to self.unit
            decimals: Number of decimal places to display

        Returns:
            Formatted size string with unit
        """
        unit = unit or self.unit
        divisor = self.unit_multipliers[unit]
        formatted = f"{size_bytes/divisor:.{decimals}f}"
        if show_unit:
            formatted+=f" {unit}"
        return formatted

    def format_block_index_range(self, from_block, to_block):
        """
        Format a block index range with proper alignment

        Args:
            from_block: Starting block index
            to_block: Ending block index

        Returns:
            Formatted block index range string (e.g. "5/123")
        """
        width = len(str(self.total_blocks))

        # We need to format each part separately to avoid f-string issues
        from_part = f"{from_block:{width}}"
        to_part = f"{to_block:{width}}"
        formatted = f"{from_part}/{to_part}"
        return formatted


    def calc_block_range_size_bytes(self, from_block: int, to_block: int) -> int:
        """
        Calculate total number of bytes in a block range.

        Args:
            from_block: First block index
            to_block: Last block index (inclusive)

        Returns:
            Total number of bytes in the specified block range
        """
        if to_block is None:
            to_block=self.total_blocks
        if to_block >= self.total_blocks:
            to_block = self.total_blocks - 1

        full_blocks = max(0, to_block - from_block)
        last_block_size = self.last_block_size if to_block == self.total_blocks - 1 else self.blocksize_bytes
        total_bytes = full_blocks * self.blocksize_bytes + last_block_size
        return total_bytes


    def get_progress_bar(self, from_block: int, to_block: int = None):
        total_bytes = self.calc_block_range_size_bytes(from_block, to_block)
        bar = tqdm(total=total_bytes, unit="B", unit_scale=True)
        bar.set_description(f"Processing {self.name}")
        bar.update(0)
        return bar
