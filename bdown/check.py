#!/usr/bin/env python3
#!/usr/bin/env python3
"""
Block-based file integrity checker and
metadata generator to be used with blockdownload

Usage:
  Generate .yaml metadata:
    dcheck --url URL --create [--blocksize SIZE] [--unit UNIT] file

  Compare two files:
    dcheck --url URL file1 file2 [--head-only]

  Compare two .yaml files:
    dcheck --url URL file1.yaml file2.yaml [--head-only]

Created on 2025-05-06
Author: wf
"""
import argparse
import os
from dataclasses import dataclass, field

from bdown.block import Block, Status, StatusSymbol
from bdown.block_fiddler import BlockFiddler
from bdown.download import BlockDownload


@dataclass
class BlockCheck(BlockFiddler):
    """
    check downloaded blocks
    """

    file1: str = None
    file2: str = None
    head_only: bool = False
    create: bool = False
    status: Status = field(default_factory=Status)

    def __post_init__(self):
        self.file1 = os.path.abspath(self.file1)
        if self.file2:
            self.file2 = os.path.abspath(self.file2)
        self.size = os.path.getsize(self.file1)
        super().__post_init__()

    def get_or_create_yaml(self, path: str, url: str):
        """
        get or create a yaml file for the given path and url
        """
        yaml_path = path + ".yaml"
        print(
            f"Processing {path}... (file size: {os.path.getsize(path) / (1024**3):.2f} GB)"
        )
        if os.path.exists(yaml_path):
            bd = BlockDownload.ofYamlPath(yaml_path)
        else:
            bd = BlockDownload(
                name=os.path.basename(path),
                url=url,
                blocksize=self.blocksize,
                unit=self.unit,
            )
            file_size = os.path.getsize(path)
            if not file_size == bd.size:
                msg = f"file size mismatch file:{file_size} != download url {bd.size}"
                raise Exception(msg)
            from_block = 0
            _, to_block, _ = bd.compute_total_bytes(from_block)
            progress = bd.get_progress_bar(from_block, to_block)
            with progress:
                for index, start, end in bd.block_ranges(from_block, to_block):
                    block = Block(
                        block=index, offset=start, path=os.path.basename(path)
                    )
                    block.size = end - start + 1
                    block.md5_head = block.calc_md5(
                        os.path.dirname(path), chunk_limit=1, seek_to_offset=True
                    )
                    if not self.head_only:
                        block.md5 = block.calc_md5(
                            os.path.dirname(path),
                            progress_bar=progress,
                            seek_to_offset=True,
                        )
                    bd.blocks.append(block)
                    block_range = self.format_block_index_range(index, to_block)
                    from_size = self.format_size(start, unit="GB", show_unit=False)
                    to_size = self.format_size(end, unit="GB")
                    desc = f"MD5 {block_range} {from_size}-{to_size}"
                    progress.set_description(desc)
                    if self.head_only:
                        progress.update(bd.blocksize_bytes)
            bd.yaml_path = yaml_path
            bd.sort_blocks()
            bd.save()
            formatted_size = bd.format_size(bd.size)
            msg = f"{yaml_path} created with {bd.total_blocks} blocks ({formatted_size} processed)"
            print(msg)
        return bd

    def generate_yaml(self, url: str):
        self.get_or_create_yaml(path=self.file1, url=url)

    def compare(self, url=None):
        """
        Compare two files or two YAML files

        Args:
            url: Optional URL for reference
        """
        # Check if both files are YAML files
        if self.file1.endswith(".yaml") and self.file2.endswith(".yaml"):
            # Compare two YAML files directly
            self.compare_yaml_files(self.file1, self.file2)
        else:
            # Original comparison logic for regular files
            bd1 = self.get_or_create_yaml(self.file1, url=url)
            bd2 = self.get_or_create_yaml(self.file2, url=url)
            self.compare_block_downloads(bd1, bd2)

    def compare_yaml_files(self, yaml_file1, yaml_file2):
        """
        Compare two YAML files directly

        Args:
            yaml_file1: Path to first YAML file
            yaml_file2: Path to second YAML file
        """
        bd1 = BlockDownload.ofYamlPath(yaml_file1)
        bd2 = BlockDownload.ofYamlPath(yaml_file2)
        self.compare_block_downloads(bd1, bd2)

    def compare_block_downloads(self, bd1, bd2):
        """
        Compare two BlockDownload instances

        Args:
            bd1: First BlockDownload instance
            bd2: Second BlockDownload instance
        """
        b1 = {b.block: b for b in bd1.blocks}
        b2 = {b.block: b for b in bd2.blocks}
        common = sorted(set(b1.keys()) & set(b2.keys()))
        if not common:
            print("⚠️  No common block indices between the two BlockDownload instances.")
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

                self.status.update(symbol, i)
                self.status.set_description(progress)
                progress.update(bd1.blocksize_bytes)

        print("\nFinal:", self.status.summary())


def parse_args():
    parser = argparse.ArgumentParser(
        description="Check block-level integrity of files downloaded using blockdownload .yaml metadata."
    )
    parser.add_argument("--url", required=True, help="Download URL to check against")
    parser.add_argument(
        "file",
        nargs="+",
        help="File(s) to process (1=create, 2=compare - either by creating yamls for two downloads or by supplying two yaml files)",
    )
    parser.add_argument(
        "--create", action="store_true", help="Generate .yaml for one file"
    )
    parser.add_argument(
        "--blocksize", type=int, default=500, help="Block size in units (default: 500)"
    )
    parser.add_argument(
        "--unit", choices=["KB", "MB", "GB"], default="MB", help="Block size unit"
    )
    parser.add_argument("--head-only", action="store_true", help="Use md5_head only")
    return parser.parse_args()


def main():
    args = parse_args()
    files = args.file
    checker = BlockCheck(
        name=os.path.basename(files[0]),
        file1=files[0],
        file2=files[1] if len(files) == 2 else None,
        blocksize=args.blocksize,
        unit=args.unit,
        head_only=args.head_only,
        create=args.create,
    )
    if args.create and len(files) == 1:
        checker.generate_yaml(args.url)
    elif len(files) == 2:
        checker.compare(args.url)
    else:
        print("Usage:\n  check.py --create file\n  check.py file1 file2 [--head-only]")


if __name__ == "__main__":
    main()
