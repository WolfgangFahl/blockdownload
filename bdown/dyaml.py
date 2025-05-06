#!/usr/bin/env python3
"""
Command-line tool to generate .yaml metadata files for block-based file verification.

This script uses the existing BlockDownload and Block APIs to compute and store
md5_head and optionally full md5 for each block of a given file.

Created on 2025-05-06

@author: wf
"""

import argparse
import os

from bdown.download import BlockDownload, Block


def create_yaml(file_path, blocksize, unit, head_only):
    """
    Create a YAML metadata file with BlockDownload and Block entries for a given file.

    Args:
        file_path (str): Path to the file to analyze.
        blocksize (int): Block size value (unit specified separately).
        unit (str): Unit of block size, must be 'KB', 'MB', or 'GB'.
        head_only (bool): If True, only calculate md5_head, skip full md5.
    """
    name = os.path.basename(file_path)
    size = os.path.getsize(file_path)
    base_path = os.path.dirname(file_path)
    part_path = os.path.basename(file_path)

    bd = BlockDownload(name=name, url=file_path, blocksize=blocksize, unit=unit)
    bd.size = size

    for index, start, end in bd.block_ranges(0, None):
        block = Block(block=index, offset=start, path=part_path)
        block.md5_head = block.calc_md5(base_path, chunk_limit=1)
        if not head_only:
            block.md5 = block.calc_md5(base_path, chunk_limit=None)
        bd.blocks.append(block)

    yaml_path = file_path + ".yaml"
    bd.save_to_yaml_file(yaml_path)
    print(f"Wrote {yaml_path} with {len(bd.blocks)} blocks.")


def parse_args():
    parser = argparse.ArgumentParser(
        description="Create .yaml metadata for block-based file verification."
    )
    parser.add_argument("file", help="Path to the file to analyze")
    parser.add_argument("--create", action="store_true", help="Generate .yaml metadata for the file")
    parser.add_argument("--blocksize", type=int, default=10, help="Block size (default: 10)")
    parser.add_argument("--unit", choices=["KB", "MB", "GB"], default="MB", help="Unit for block size (default: MB)")
    parser.add_argument("--head-only", action="store_true", help="Only compute md5_head, skip full md5")
    return parser.parse_args()


def main():
    args = parse_args()
    if args.create:
        create_yaml(args.file, args.blocksize, args.unit, args.head_only)
    else:
        print("Error: --create required for metadata generation. Comparison not yet implemented.")


if __name__ == "__main__":
    main()
