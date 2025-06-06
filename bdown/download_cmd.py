"""
Command-line interface for BlockDownload

Created on 2025-05-05

@author: wf
"""

import argparse
import os
from argparse import Namespace

from bdown.download import BlockDownload


class BlockDownloadWorker:
    """
    command line interface options for block download
    """

    def __init__(self, downloader: BlockDownload, args: Namespace):
        self.downloader = downloader
        self.args = args
        self.from_block = args.from_block
        self.to_block = args.to_block
        if args.progress:
            self.progress_bar = downloader.get_progress_bar(
                from_block=self.from_block, to_block=self.to_block
            )
        else:
            self.progress_bar = None

    def work_with_progress(self):
        if self.args.progress:
            with self.progress_bar:
                self.work()
        else:
            self.work()

    def work(self):
        """
        handle the command line arguments
        """
        if self.need_download:
            if self.progress_bar:
                mode="Patching" if self.args.patch else "Downloading"
                self.progress_bar.set_description(mode)
            self.downloader.download(
                target=self.args.target,
                from_block=self.from_block,
                to_block=self.to_block,
                boost=self.args.boost,
                progress_bar=self.progress_bar,
                force=self.args.force
            )
        if self.args.split:
            from bdown.filesplitter import FileSplitter
            splitter = FileSplitter(
                name=self.args.name,
                blocksize=self.args.blocksize,
                unit=self.args.unit,
            )
            splitter.split(
                filepath=self.args.split,
                target_dir=self.args.target,
                progress_bar=self.progress_bar,
            )

        if self.args.output:
            # Check if output file exists and force flag is not set
            if os.path.exists(self.args.output) and not self.args.force:
                print(
                    f"Error: Output file {self.args.output} already exists. Use --force to overwrite."
                )
                return

            # Update progress bar for reassembly if it exists
            if self.progress_bar:
                # Reset the progress to start from zero
                self.progress_bar.reset()
                self.progress_bar.set_description("Creating target")

            # Reassemble blocks into output file
            md5 = self.downloader.reassemble(
                parts_dir=self.args.target,
                output_path=self.args.output,
                progress_bar=self.progress_bar,
                on_the_fly=self.args.on_the_fly,
                timeout=self.args.timeout,
            )
            if md5:
                self.downloader.md5 = md5
                self.downloader.save(update_md5_from_total_hash=False)

            print(f"File reassembled successfully: {self.args.output}")


def main():
    parser = argparse.ArgumentParser(
        description="Segmented file downloader using HTTP range requests."
    )
    parser.add_argument("url", help="URL to download from")
    parser.add_argument("target", help="Target directory to store .part files")
    parser.add_argument(
        "--name",
        required=True,
        help="Name for the download session (used for .yaml control file)",
    )
    parser.add_argument(
        "--blocksize",
        type=int,
        default=32,
        help="Block size (default: 32)"
    )
    parser.add_argument(
        "--unit",
        choices=["KB", "MB", "GB"],
        default="MB",
        help="Block size unit (default: MB)",
    )
    parser.add_argument("--from-block", type=int, default=0, help="First block index")
    parser.add_argument("--to-block", type=int, help="Last block index (inclusive)")
    parser.add_argument(
        "--boost",
        type=int,
        default=1,
        help="Number of concurrent download threads (default: 1)",
    )
    parser.add_argument(
        "--force", action="store_true", help="Overwrite output file if it exists"
    )
    parser.add_argument(
        "-otf",
        "--on-the-fly", action="store_true",
        help="Reassemble blocks on-the-fly as they become available during download"
    )
    parser.add_argument(
        "--progress", action="store_true", help="Show tqdm progress bar"
    )
    parser.add_argument(
        "--patch", action="store_true", help="patch missing blocks"
    )
    parser.add_argument(
        "--split",
        help="Path to local file to split instead of downloading"
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=300.0,
        help="Timeout in seconds when waiting for blocks (default: 300.0)"
    )

    parser.add_argument(
        "--yaml", help="Path to the YAML metadata file (for standalone reassembly)"
    )

    parser.add_argument(
        "--output", help="Path where the final target file will be saved"
    )

    args = parser.parse_args()
    os.makedirs(args.target, exist_ok=True)
    if args.yaml:
        yaml_path = args.yaml
    else:
        yaml_path = os.path.join(args.target, f"{args.name}.yaml")
    if os.path.exists(yaml_path):
        downloader = BlockDownload.ofYamlPath(yaml_path)
        need_download = args.patch
    else:
        downloader = BlockDownload(
            name=args.name, url=args.url, blocksize=args.blocksize, unit=args.unit
        )
        need_download = True
    downloader.yaml_path = yaml_path
    worker = BlockDownloadWorker(downloader, args)
    worker.need_download = need_download
    worker.work_with_progress()


if __name__ == "__main__":
    main()
