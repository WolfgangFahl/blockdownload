"""
Created on 2025-05-21

@author: wf
"""
import os

from bdown.block import Block, BlockIterator
from bdown.block_fiddler import BlockFiddler
from lodstorage.yamlable import lod_storable


@lod_storable
class FileSplitter(BlockFiddler):
    """
    Specialized BlockFiddler for splitting files into blocks
    """

    def split(self, file_path: str, target_dir: str, progress_bar=None):
        """
        Split a file into blocks and save as part files

        Args:
            file_path: Path to the file to split
            target_dir: Directory to store part files
            progress_bar: Optional progress bar
        """
        # Update file size from input file
        self.size = os.path.getsize(file_path)
        os.makedirs(target_dir, exist_ok=True)

        # Process each block
        for i in range(self.total_blocks):
            start = i * self.blocksize_bytes
            end = min(start + self.blocksize_bytes - 1, self.size - 1)
            block_size = end - start + 1

            # Create part filename
            part_name = f"{self.name}-{i:04d}.part"
            part_path = os.path.join(target_dir, part_name)

            # Create BlockIterator configuration
            with open(part_path, "wb") as target_file:
                bi = BlockIterator(
                    index=i,
                    offset=start,
                    size=block_size,
                    block_path=part_name,
                    progress_bar=progress_bar,
                    target_file=target_file,
                    chunk_size=self.chunk_size,
                    hash_total=self.total_hash
                )

                block = Block.ofFile(bi, file_path)

            # Save block metadata
            block_yaml_path = os.path.join(target_dir, f"{self.name}-{i:04d}.yaml")
            block.save_to_yaml_file(block_yaml_path)
            self.blocks.append(block)

        # Save metadata
        self.sort_blocks()
        self.yaml_path = os.path.join(target_dir, f"{self.name}.yaml")
        self.save()