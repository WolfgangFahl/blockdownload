'''
Created on 2025-05-06

@author: wf
'''
from lodstorage.yamlable import lod_storable
import hashlib
import os
import requests
from enum import Enum

class StatusSymbol(Enum):
    SUCCESS = "✅"
    FAIL = "❌"
    WARN = "⚠️"

class Status:
    """
    Track block comparison results and provide symbolic summary.
    """
    def __init__(self):
        self.symbol_blocks = {
            symbol: set() for symbol in StatusSymbol
        }

    def update(self, symbol: StatusSymbol, index: int):
        self.symbol_blocks[symbol].add(index)

    def summary(self) -> str:
        return " ".join(
            f"{len(self.symbol_blocks[symbol])}{symbol.value}"
            for symbol in StatusSymbol
        )

    def set_description(self, progress_bar):
        progress_bar.set_description(self.summary())


@lod_storable
class Block:
    """
    A single download block.
    """

    block: int
    path: str
    offset: int
    md5: str = None  # full md5 hash
    md5_head: str = None  # hash of first chunk

    def calc_md5(self, base_path: str, chunk_size: int = 8192, chunk_limit: int = None) -> str:
        """
        Calculate the MD5 checksum of this block's file.

        Args:
            base_path: Directory where the block's relative path is located.
            chunk_size: Bytes per read operation (default: 8192).
            chunk_limit: Maximum number of chunks to read (e.g. 1 for md5_head).

        Returns:
            str: The MD5 hexadecimal digest.
        """
        full_path = os.path.join(base_path, self.path)
        hash_md5 = hashlib.md5()
        index = 0

        with open(full_path, "rb") as f:
            for chunk in iter(lambda: f.read(chunk_size), b""):
                hash_md5.update(chunk)
                index += 1
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
    def ofResponse(
        cls,
        block_index: int,
        offset: int,
        chunk_size: int,
        target_path: str,
        response: requests.Response,
        progress_bar=None,
    ) -> "Block":
        """
        Create a Block from a download HTTP response.

        Args:
            block_index: Index of the block.
            offset: Byte offset within the full file.
            target_path: Path to the .part file to write.
            response: The HTTP response streaming the content.
            progress_bar: optional progress_bar for reporting download progress.

        Returns:
            Block: The constructed block with calculated md5.
        """
        hash_md5 = hashlib.md5()
        hash_head = hashlib.md5()
        first = True
        block_path=os.path.basename(target_path)
        if progress_bar:
            progress_bar.set_description(block_path)
        with open(target_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=chunk_size):
                f.write(chunk)
                hash_md5.update(chunk)
                if first:
                    hash_head.update(chunk)
                    first = False
                if progress_bar:
                    progress_bar.update(len(chunk))
        block = cls(
            block=block_index,
            path=block_path,
            offset=offset,
            md5=hash_md5.hexdigest(),
            md5_head=hash_head.hexdigest(),
        )
        return block