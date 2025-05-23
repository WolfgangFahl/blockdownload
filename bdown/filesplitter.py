"""
Created on 2025-05-21

@author: wf
"""
import os
from lodstorage.yamlable import lod_storable
from bdown.block import Block
from bdown.block_fiddler import BlockFiddler

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

            # Create block from file
            block = Block.ofFile(
                block_index=i,
                offset=start,
                size=block_size,
                chunk_size=self.chunk_size,
                source_path=file_path,
                target_path=part_path,
                progress_bar=progress_bar
            )

            # Save block metadata
            block_yaml_path = os.path.join(target_dir, f"{self.name}-{i:04d}.yaml")
            block.save_to_yaml_file(block_yaml_path)
            self.blocks.append(block)

        # Save metadata
        self.sort_blocks()
        self.yaml_path = os.path.join(target_dir, f"{self.name}.yaml")
        self.save()