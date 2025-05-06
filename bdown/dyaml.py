#!/usr/bin/env python3
"""
Block-level metadata generator and future comparison tool.

Usage:
    check.py --create --blocksize 10 --unit MB data.jnl

Creates a BlockDownload-compatible .yaml metadata file for block-wise integrity verification.

Created on 2025-05-06
Author: wf
"""

import argparse
import os

from bdown.download import BlockDownload, Block


class DYaml:
    """
    YAML metadata generator for block-based file verification using BlockDownload.
    """

    def __init__(self, file_path, blocksize, unit, head_only):
        """
        Initialize the generator with the given configuration.

        Args:
            file_path (str): Path to the file to analyze.
            blocksize (int): Block size in unit multiples.
            unit (str): Unit for block size ('KB', 'MB', 'GB').
            head_only (bool): Whether to only calculate md5_head.
        """
        self.file_path = os.path.abspath(file_path)
        self.blocksize = blocksize
        self.unit = unit
        self.head_only = head_only
        self.file_size = os.path.getsize(self.file_path)
        self.base_path = os.path.dirname(self.file_path)
        self.part_path = os.path.basename(self.file_path)

    def create(self):
        """
        Generate a BlockDownload .yaml file by iterating over block_ranges.
        """
        bd = BlockDownload(
            name=self.part_path,
            url=self.file_path,
            blocksize=self.blocksize,
            unit=self.unit
        )
        bd.size = self.file_size

        from_block = 0
        _, to_block, _ = bd.compute_total_bytes(from_block)

        for index, start, end in bd.block_ranges(from_block, to_block):
            block = Block(block=index, offset=start, path=self.part_path)
            block.md5_head = block.calc_md5(self.base_path, chunk_limit=1)
            if not self.head_only:
                block.md5 = block.calc_md5(self.base_path)
            bd.blocks.append(block)

        yaml_path = self.file_path + ".yaml"
        bd.save_to_yaml_file(yaml_path)
        print(f"Wrote {yaml_path} with {len(bd.blocks)} blocks.")


def parse_args():
    parser = argparse.ArgumentParser(
        description="Block integrity checker and .yaml metadata generator."
    )
    parser.add_argument("file", help="File to process")
    parser.add_argument("--create", action="store_true", help="Generate .yaml metadata for the file")
    parser.add_argument("--blocksize", type=int, default=10, help="Block size (default: 10)")
    parser.add_argument("--unit", choices=["KB", "MB", "GB"], default="MB", help="Unit for block size")
    parser.add_argument("--head-only", action="store_true", help="Only compute md5_head")
    return parser.parse_args()


def main():
    args = parse_args()
    if args.create:
        dyaml = DYaml(args.file, args.blocksize, args.unit, args.head_only)
        dyaml.create()
    else:
        print("Error: --create required. Comparison mode not yet implemented.")


if __name__ == "__main__":
    main()
