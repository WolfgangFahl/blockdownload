#!/usr/bin/env python3
# check two files for being the same by inspecting
# sample blocks with a given pattern
# this is e.g. useful with aria2 downloads which have a non sequential order
# of download
#
# The script compares blocks of two files at specified offsets using MD5 hashes.
# It supports sampling patterns such as linear, logarithmic, or full scan.
# This allows fast verification of large files (e.g. multi-GB or TB scale) that may
# have been downloaded non-sequentially or partially, enabling early
# detection of corruptions or mismatches without full byte-by-byte scans.

import argparse
import hashlib
import os
import sys
from collections import Counter

try:
    from tqdm import tqdm
except ImportError:
    tqdm = None

CHECK = "✅"
WARN = "⚠️"
FAIL = "❌"


class Check:
    """
    check a download
    """

    def __init__(self, args):
        self.args = args
        self.size1 = os.path.getsize(args.file1)
        self.size2 = os.path.getsize(args.file2)
        self.blocksize = args.blocksize
        self.max_mb = min(self.size1, self.size2) // (1024 * 1024) - 1
        self.offsets = self.calculate_offsets()
        self.status_counter = Counter()
        self.quiet = len(self.offsets) > 20

    def calculate_offsets(self):
        start = self.args.start
        step = self.args.step
        count = self.args.count
        factor = self.args.factor
        mode = self.args.mode

        if mode in ("linear", "log"):
            if step is None:
                sys.exit("Error: --step is required for linear/log mode")
            i = 0
            offsets = []
            while True:
                if mode == "linear":
                    mb = start + int(i * step)
                else:
                    base = factor if factor is not None else step
                    mb = start + int(round(base**i))
                if count is not None and i >= count:
                    break
                if mb > self.max_mb:
                    break
                offsets.append(mb)
                i += 1
            return [mb * 1024 * 1024 for mb in offsets]

        elif mode == "full":
            return [mb * 1024 * 1024 for mb in range(0, self.max_mb + 1)]

        else:
            sys.exit(f"Unsupported mode: {mode}")

    def is_zero_block(self, data):
        return all(b == 0 for b in data)

    def read_block(self, f, offset):
        f.seek(offset)
        return f.read(self.blocksize)

    def status(self, index, symbol, offset_mb, message):
        self.status_counter[symbol] += 1
        if not self.quiet:
            print(f"[{index:3}] {offset_mb:7,} MB  {symbol}  {message}")

    def run(self):
        with open(self.args.file1, "rb") as f1, open(self.args.file2, "rb") as f2:
            iterator = enumerate(self.offsets)
            if self.quiet and tqdm:
                iterator = tqdm(iterator, total=len(self.offsets))
            for i, offset in iterator:
                offset_mb = offset // (1024 * 1024)
                b1 = self.read_block(f1, offset)
                b2 = self.read_block(f2, offset)

                if (
                    not b1
                    or not b2
                    or len(b1) < self.blocksize
                    or len(b2) < self.blocksize
                ):
                    self.status(i, FAIL, offset_mb, "could not read full block")
                    continue

                zero1 = self.is_zero_block(b1)
                zero2 = self.is_zero_block(b2)
                if zero1 or zero2:
                    who = []
                    if zero1:
                        who.append("file1")
                    if zero2:
                        who.append("file2")
                    self.status(i, WARN, offset_mb, f"zero block in {', '.join(who)}")
                    continue

                md5_1 = hashlib.md5(b1).hexdigest()
                md5_2 = hashlib.md5(b2).hexdigest()
                if md5_1 == md5_2:
                    self.status(i, CHECK, offset_mb, "MD5 match")
                else:
                    self.status(i, FAIL, offset_mb, "MD5 mismatch")
                    if not self.quiet:
                        print(f"           file1: {md5_1}")
                        print(f"           file2: {md5_2}")

        print()
        print("Summary:", dict(self.status_counter))


def parse_args():
    parser = argparse.ArgumentParser(
        description="Compare blocks of two files using MD5 and UTF-8 status"
    )
    parser.add_argument("file1", help="First file to compare")
    parser.add_argument("file2", help="Second file to compare")
    parser.add_argument(
        "--start", type=int, default=0, help="Start offset in MB (default: 0)"
    )
    parser.add_argument("--step", type=float, help="Step size or factor for linear/log")
    parser.add_argument("--mode", choices=["linear", "log", "full"], required=True)
    parser.add_argument("--factor", type=float, help="Override factor for log mode")
    parser.add_argument("--count", type=int, help="Limit number of blocks (optional)")
    parser.add_argument("--blocksize", type=int, default=1024 * 1024)
    return parser.parse_args()


def main():
    args = parse_args()
    Check(args).run()


if __name__ == "__main__":
    main()
