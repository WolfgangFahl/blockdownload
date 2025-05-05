"""
Command-line interface for BlockDownload

Created on 2025-05-05

@author: wf
"""

import argparse
import os

from tqdm import tqdm

from bdown.download import BlockDownload


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
        "--blocksize", type=int, default=10, help="Block size (default: 10)"
    )
    parser.add_argument(
        "--unit",
        choices=["KB", "MB", "GB"],
        default="MB",
        help="Block size unit (default: MB)",
    )
    parser.add_argument("--from-block", type=int, default=0, help="First block index")
    parser.add_argument("--to-block", type=int, help="Last block index (inclusive)")
    parser.add_argument("--boost", type=int, default=1, help="Number of concurrent download threads (default: 1)")
    parser.add_argument(
        "--progress", action="store_true", help="Show tqdm progress bar"
    )

    args = parser.parse_args()
    os.makedirs(args.target, exist_ok=True)
    yaml_path = os.path.join(args.target, f"{args.name}.yaml")
    if os.path.exists(yaml_path):
        downloader = BlockDownload.ofYamlPath(yaml_path)
    else:
        downloader = BlockDownload(
            name=args.name,
            url=args.url,
            blocksize=args.blocksize, unit=args.unit
        )
    downloader.yaml_path = yaml_path

    if args.progress:
        from_block = args.from_block
        to_block = args.to_block
        progress_bar = downloader.get_progress_bar(from_block=from_block, to_block=to_block)
        progress_bar.set_description("Downloading")
        with progress_bar:
            downloader.download(
                target=args.target,
                from_block=from_block,
                to_block=to_block,
                boost=args.boost,
                progress_bar=progress_bar
            )
    else:
        downloader.download(
            target=args.target,
            from_block=args.from_block,
            to_block=args.to_block,
            boost=args.boost
        )


if __name__ == "__main__":
    main()
