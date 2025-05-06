#!/usr/bin/env python3
"""
Block-based file integrity checker and metadata generator.

Usage:
  Generate .yaml:
    check.py --create --blocksize 500 --unit MB data.jnl

  Compare two files:
    check.py file1 file2 [--head-only]

Created on 2025-05-06
Author: wf
"""

import argparse
import os

from bdown.download import Block, BlockDownload, Status, StatusSymbol


class BlockCheck:
    """
    check downloaded blocks
    """
    def __init__(self, file1, file2=None, blocksize=500, unit="MB", head_only=False, create=False):
        self.file1 = os.path.abspath(file1)
        self.file2 = os.path.abspath(file2) if file2 else None
        self.blocksize = blocksize
        self.unit = unit
        self.head_only = head_only
        self.create = create
        self.status = Status()

    def get_or_create_yaml(self, path):
        """
        get or create a yaml file for the given path
        """
        yaml_path = path + ".yaml"
        print(f"Processing {path}...")
        if os.path.exists(yaml_path):
            bd = BlockDownload.ofYamlPath(yaml_path)
        else:
            bd = BlockDownload(
                name=os.path.basename(path),
                url=path,
                blocksize=self.blocksize,
                unit=self.unit
            )
            bd.size = os.path.getsize(path)
            from_block = 0
            _, to_block, _ = bd.compute_total_bytes(from_block)
            progress = bd.get_progress_bar(from_block, to_block)
            with progress:
                for index, start, end in bd.block_ranges(from_block, to_block):
                    block = Block(block=index, offset=start, path=os.path.basename(path))
                    block.size = end - start + 1
                    block.md5_head = block.calc_md5(os.path.dirname(path), chunk_limit=1)
                    if not self.head_only:
                        block.md5 = block.calc_md5(os.path.dirname(path))
                    bd.blocks.append(block)
                    desc=f"{block}"
                    progress.set_description(desc)
                    progress.update(bd.blocksize_bytes)
            bd.yaml_path = yaml_path
            bd.save()
            print(f"{yaml_path} created with ")
        return bd

    def generate_yaml(self):
        self.get_or_create_yaml(self.file1)

    def compare(self):
        bd1 = self.get_or_create_yaml(self.file1)
        bd2 = self.get_or_create_yaml(self.file2)

        b1 = {b.block: b for b in bd1.blocks}
        b2 = {b.block: b for b in bd2.blocks}
        common = sorted(set(b1.keys()) & set(b2.keys()))
        if not common:
            return

        _, to_block, _ = bd1.compute_total_bytes(0)
        progress = bd1.get_progress_bar(0, to_block)

        with progress:
            for i in common:
                block1 = b1[i]
                block2 = b2[i]

                md5_1 = block1.md5_head if self.head_only else block1.md5
                md5_2 = block2.md5_head if self.head_only else block2.md5
                if md5_1 is None or md5_2 is None:
                    symbol = StatusSymbol.WARN
                elif md5_1 == md5_2:
                    symbol = StatusSymbol.SUCCESS
                else:
                    symbol = StatusSymbol.FAIL

                symbol = StatusSymbol.SUCCESS if md5_1 == md5_2 else StatusSymbol.FAIL
                self.status.update(symbol, i)
                # all blocks have the same blocksize except the last
                # for progress display this is good enough
                self.status.set_description(progress)
                progress.update(bd1.blocksize_bytes)

        print("\nFinal:", self.status.summary())


def parse_args():
    parser = argparse.ArgumentParser(
        description="Check block-level integrity of files using .yaml metadata."
    )
    parser.add_argument("file", nargs="+", help="File(s) to process (1=create, 2=compare)")
    parser.add_argument("--create", action="store_true", help="Generate .yaml for one file")
    parser.add_argument("--blocksize", type=int, default=500, help="Block size in units (default: 500)")
    parser.add_argument("--unit", choices=["KB", "MB", "GB"], default="MB", help="Block size unit")
    parser.add_argument("--head-only", action="store_true", help="Use md5_head only")
    return parser.parse_args()


def main():
    args = parse_args()
    files = args.file
    checker = BlockCheck(
        file1=files[0],
        file2=files[1] if len(files) == 2 else None,
        blocksize=args.blocksize,
        unit=args.unit,
        head_only=args.head_only,
        create=args.create
    )
    if args.create and len(files) == 1:
        checker.generate_yaml()
    elif len(files) == 2:
        checker.compare()
    else:
        print("Usage:\n  check.py --create file\n  check.py file1 file2 [--head-only]")


if __name__ == "__main__":
    main()
