"""
Created on 2025-05-06

@author: wf
"""

import hashlib
import os
from dataclasses import dataclass, field
from typing import List, Tuple

from tqdm import tqdm

from bdown.block import Block


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
        blocksize_bytes = self.blocksize * self.unit_multipliers[self.unit]
        return blocksize_bytes

    @property
    def total_blocks(self) -> int:
        if self.size is None:
            raise ValueError("total file size must be set")
        total_blocks = (self.size + self.blocksize_bytes - 1) // self.blocksize_bytes
        return total_blocks

    @property
    def last_block_size(self) -> int:
        total_blocks = self.total_blocks
        if total_blocks == 0:
            last_block_size = 0
        else:
            same_size_total = (total_blocks - 1) * self.blocksize_bytes
            last_block_size = self.size - same_size_total
        return last_block_size

    def sort_blocks(self):
        """
        Sort the blocks list by block index
        """
        self.blocks.sort(key=lambda b: b.block)

    def format_size(self, size_bytes, unit=None, decimals=2, show_unit: bool = True):
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
            formatted += f" {unit}"
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
            to_block = self.total_blocks
        if to_block >= self.total_blocks:
            to_block = self.total_blocks - 1

        full_blocks = max(0, to_block - from_block)
        last_block_size = (
            self.last_block_size
            if to_block == self.total_blocks - 1
            else self.blocksize_bytes
        )
        total_bytes = full_blocks * self.blocksize_bytes + last_block_size
        return total_bytes

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
        result = []
        block_size = self.blocksize_bytes
        for index in range(from_block, to_block + 1):
            start = index * block_size
            end = min(start + block_size - 1, self.size - 1)
            result.append((index, start, end))
        return result

    def compute_total_bytes(
        self, from_block: int, to_block: int = None
    ) -> Tuple[int, int, int]:
        """
        Compute the total number of bytes to download for a block range.

        Args:
            from_block: First block index.
            to_block: Last block index (inclusive), or None for all blocks.

        Returns:
            Tuple of (from_block, to_block, total_bytes).
        """
        total_blocks = (self.size + self.blocksize_bytes - 1) // self.blocksize_bytes
        if to_block is None or to_block >= total_blocks:
            to_block = total_blocks - 1

        total_bytes = 0
        for _, start, end in self.block_ranges(from_block, to_block):
            total_bytes += end - start + 1

        return from_block, to_block, total_bytes

    def get_progress_bar(self, from_block: int, to_block: int = None):
        total_bytes = self.calc_block_range_size_bytes(from_block, to_block)
        bar = tqdm(total=total_bytes, unit="B", unit_scale=True)
        bar.set_description(f"Processing {self.name}")
        bar.update(0)
        return bar

    def reassemble(
        self,
        parts_dir: str,
        output_path: str,
        progress_bar=None,
        force=False,
        compute_md5=True,
    ) -> str:
        """
        Reassemble a complete file from my blocks

        Args:
            parts_dir: Directory containing part files
            output_path: Path where reassembled file will be saved
            progress_bar: Optional progress bar
            force: If True, overwrite existing file without warning
            compute_md5: If True, compute MD5 while copying

        Returns:
            The hex digest of the MD5 checksum if computed, else None
        """
        if os.path.exists(output_path) and not force:
            raise FileExistsError(
                f"Output file {output_path} already exists. Please specify a different path, use force=True, or remove the existing file first."
            )

        with open(output_path, "wb") as f:
            f.truncate(self.size)

        self.sort_blocks()
        total = 0
        md5 = hashlib.md5() if compute_md5 else None

        for block in self.blocks:
            block_size = block.copy_to(parts_dir, output_path, md5=md5)
            total += block_size
            if progress_bar:
                progress_bar.update(block_size)

        total_str = self.format_size(total)
        msg = f"created {output_path} - {total_str}"
        md5_hex = None
        if md5:
            md5_hex = md5.hexdigest()
            msg += f"\nmd5: {md5_hex}"
        print(msg)
        return md5_hex
