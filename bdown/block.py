"""
Created on 2025-05-06

@author: wf
"""

import hashlib
import os
from enum import Enum
from typing import Optional
from dataclasses import dataclass
import requests
from lodstorage.yamlable import lod_storable
from tqdm import tqdm as Progressbar

class StatusSymbol(Enum):
    """
    utf-8 status symbols
    """
    SUCCESS = "✅"
    FAIL = "❌"
    WARN = "⚠️"

class Status:
    """
    Track block comparison results and provide symbolic summary.
    """

    def __init__(self):
        self.symbol_blocks = {symbol: set() for symbol in StatusSymbol}

    def update(self, symbol: StatusSymbol, index: int):
        self.symbol_blocks[symbol].add(index)

    def count(self, symbol: StatusSymbol) -> int:
        """Returns count of blocks with given status symbol"""
        status_count = len(self.symbol_blocks[symbol])
        return status_count

    @property
    def success(self) -> bool:
        """Returns True if all blocks matched successfully with no warnings or failures"""
        success = (
            self.count(StatusSymbol.FAIL) == 0
            and self.count(StatusSymbol.WARN) == 0
            and self.count(StatusSymbol.SUCCESS) > 0
        )
        return success

    def summary(self) -> str:
        return " ".join(
            f"{len(self.symbol_blocks[symbol])}{symbol.value}"
            for symbol in StatusSymbol
        )

    def set_description(self, progress_bar):
        progress_bar.set_description(self.summary())

@dataclass
class BlockIterator:
    """
    Configuration dataclass for block processing parameters.
    """
    index: int # index of the block in the target
    offset: int # offset of the block in the outer file to be reassembled later
    size: int # size of the block
    block_path: str # relative path of the block file
    progress_bar: Optional[Progressbar] = None
    target_file: any = None
    target_offset: int = 0 # e.g. for block rechunking
    chunk_size: int=8192 # default chunk size
    hash_total: any =None

@lod_storable
class Block:
    """
    A single download block.
    """

    block: int
    path: str
    offset: int
    md5: str = ""  # full md5 hash
    md5_head: str = ""  # hash of first chunk

    def is_consistent(self, other: 'Block') -> bool:
        """Check if blocks are consistent"""
        offset_match = self.offset == other.offset
        md5_match = self.md5 == other.md5
        consistent = offset_match and md5_match
        return consistent

    def file_exists(self, base_path: str) -> bool:
        """Check if the block file exists at the expected path."""
        full_path = os.path.join(base_path, self.path)
        exists = os.path.exists(full_path)
        return exists

    def yaml_exists(self, base_path: str) -> bool:
        """Check if the yaml metadata file exists."""
        yaml_path = self.path.replace('.part', '.yaml')
        full_yaml_path = os.path.join(base_path, yaml_path)
        exists = os.path.exists(full_yaml_path)
        return exists

    def md5_matches(self, full_hash: str = None, head_hash: str = None) -> bool:
        """Check if provided hashes match stored hashes."""
        full_matches = False
        head_matches = False

        if full_hash and self.md5:
            full_matches = self.md5 == full_hash

        if head_hash and self.md5_head:
            head_matches = self.md5_head == head_hash

        # Return True if any provided hash matches
        has_full_match = full_hash and full_matches
        has_head_match = head_hash and head_matches
        matches = has_full_match or has_head_match

        return matches

    def is_valid(self, base_path: str, check_head: bool = True) -> bool:
        """Check if block file exists and passes MD5 validation."""
        file_present = self.file_exists(base_path)
        if not file_present:
            return False

        if check_head:
            chunk_limit = 1
            expected_hash = self.md5_head
        else:
            chunk_limit = None
            expected_hash = self.md5

        has_expected_hash = bool(expected_hash)
        if not has_expected_hash:
            return False

        calculated_hash = self.calc_md5(base_path, chunk_limit=chunk_limit)
        hash_valid = calculated_hash == expected_hash
        valid = file_present and hash_valid
        return valid

    def ensure_yaml(self, base_path: str):
        """Create yaml file if it doesn't exist."""
        yaml_present = self.yaml_exists(base_path)
        if not yaml_present:
            yaml_path = self.path.replace('.part', '.yaml')
            full_yaml_path = os.path.join(base_path, yaml_path)
            self.save_to_yaml_file(full_yaml_path)

    def calc_md5(
        self,
        base_path: str,
        chunk_size: int = 8192,
        chunk_limit: int = None,
        progress_bar=None,
        seek_to_offset: bool = False,
    ) -> str:
        """
        Calculate the MD5 checksum of this block's file.

        Args:
            base_path: Directory where the block's relative path is located.
            chunk_size: Bytes per read operation (default: 8192).
            chunk_limit: Maximum number of chunks to read (e.g. 1 for md5_head).
            progress_bar: if supplied update the progress_bar
            seek_to_offset: Whether seek to the block's offset (default: False) - needs to be True for non blocked complete files

        Returns:
            str: The MD5 hexadecimal digest.
        """
        full_path = os.path.join(base_path, self.path)
        hash_md5 = hashlib.md5()
        index = 0

        with open(full_path, "rb") as f:
            # seek to offset in case self.path is a large file containing multiple blocks
            if seek_to_offset:
                f.seek(self.offset)
            for chunk in iter(lambda: f.read(chunk_size), b""):
                hash_md5.update(chunk)
                index += 1
                # Update progress bar if provided
                if progress_bar:
                    progress_bar.update(len(chunk))
                if chunk_limit is not None and index >= chunk_limit:
                    break

        return hash_md5.hexdigest()

    def read_block(self, f):
        """
        Read this block from an open binary file.

        Args:
            f: File handle opened in binary mode.

        Returns:
            bytes: Block data.
        """
        f.seek(self.offset)
        data = f.read(self.size)
        return data

    def copy_to(
        self,
        parts_dir: str,
        output_path: str,
        chunk_size: int = 1024 * 1024,
        md5 = None,
    ) -> int:
        """
        Copy block data from part file to the correct offset in target file

        Args:
            parts_dir: Directory containing part files
            output_path: Path to output file where block will be copied
            chunk_size: Size of read/write chunks
            md5: Optional hashlib.md5() instance for on-the-fly update

        Returns:
            Number of bytes copied
        """
        part_path = os.path.join(parts_dir, self.path)
        bytes_copied = 0

        with open(part_path, "rb") as part_file:
            with open(output_path, "r+b") as out_file:
                out_file.seek(self.offset)
                while True:
                    chunk = part_file.read(chunk_size)
                    if not chunk:
                        break
                    out_file.write(chunk)
                    if md5:
                        md5.update(chunk)
                    bytes_copied += len(chunk)

        return bytes_copied

    @staticmethod
    def is_zero_block(data):
        """
        Check if the block data consists entirely of zero bytes.

        Args:
            data (bytes): Data read from a block.

        Returns:
            bool: True if all bytes are zero, False otherwise.
        """
        all_zero = all(b == 0 for b in data)
        result = all_zero
        return result

    def status(self, symbol, offset_mb, message, counter, quiet):
        """
        Report and count the status of an operation on this block.

        Args:
            symbol (str): Status symbol (e.g., ✅, ❌).
            offset_mb (int): Block offset in megabytes.
            message (str): Message to log.
            counter (Counter): Counter to update.
            quiet (bool): Whether to suppress output.
        """
        counter[symbol] += 1
        if not quiet:
            print(f"[{self.index:3}] {offset_mb:7,} MB  {symbol}  {message}")

    @classmethod
    def ofIterator(cls, bi: BlockIterator, chunks_iterator) -> 'Block':
        """
        Create a Block from a BlockIterator configuration and chunks iterator.

        Args:
            bi: BlockIterator configuration containing block metadata and options
            chunks_iterator: Iterator yielding data chunks to process

        Returns:
            Block: Created block with calculated MD5 hashes
        """
        hash_md5 = hashlib.md5()
        hash_head = hashlib.md5()
        first = True

        if bi.progress_bar:
            bi.progress_bar.set_description(bi.block_path)

        for chunk in chunks_iterator:
            # Optional file writing
            if bi.target_file is not None:
                bi.target_file.write(chunk)
            hash_md5.update(chunk)
            if bi.hash_total:
                bi.hash_total.update(chunk)
            if first:
                hash_head.update(chunk)
                first = False
            if bi.progress_bar:
                bi.progress_bar.update(len(chunk))

        created_block = Block(
            block=bi.index,
            path=bi.block_path,
            offset=bi.offset,
            md5=hash_md5.hexdigest(),
            md5_head=hash_head.hexdigest(),
        )
        return created_block

    @classmethod
    def ofResponse(
        cls,
        bi:BlockIterator,
        response: requests.Response,
    ) -> "Block":
        """
        Create a Block from a download HTTP response.
        """
        chunks_iterator = response.iter_content(chunk_size=bi.chunk_size)
        response_block = cls.ofIterator(
            bi, chunks_iterator=chunks_iterator
        )
        return response_block

    @classmethod
    def ofFile(
        cls,
        bi:BlockIterator,
        source_path: str,
    ) -> "Block":
        """
        Create a Block from a file.
        """
        def file_chunk_iterator():
            with open(source_path, "rb") as f:
                f.seek(bi.offset)
                bytes_read = 0
                while bytes_read < bi.size:
                    bytes_to_read = min(bi.chunk_size, bi.size - bytes_read)
                    chunk = f.read(bytes_to_read)
                    if not chunk:
                        break
                    bytes_read += len(chunk)
                    yield chunk

        file_block = cls.ofIterator(
            bi,
            chunks_iterator=file_chunk_iterator(),
        )
        return file_block