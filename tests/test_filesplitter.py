"""
Created on 2025-05-21

@author: wf
"""

import os

from bdown.download import BlockDownload

from bdown.filesplitter import FileSplitter
from tests.baseblocktest import BaseBlockTest


class TestFileSplitter(BaseBlockTest):
    """
    Test splitting a local file into part blocks.
    """

    def setUp(self, debug=True, profile=True):
        super().setUp(debug, profile)


    def test_filesplitter(self):
        """
        Split a local file into blocks and verify block count and checksum.
        """
        if not os.path.exists(self.yaml_path):
            return

        bd = BlockDownload.ofYamlPath(self.yaml_path)
        split_dir = os.path.join(self.download_dir, "split")
        os.makedirs(split_dir, exist_ok=True)

        splitter = FileSplitter(
            name=self.name,
            blocksize=bd.blocksize,
            unit=bd.unit,
        )

        splitter.split(
            file_path=self.sample_path,
            target_dir=split_dir,
            progress_bar=None,
        )

        self.assertTrue(len(splitter.blocks) > 0)
        splitter.save()
        self.assertEqual(len(splitter.blocks), len(bd.blocks), "Block count mismatch")
        # verify that the md5 of all blocks match both the splitter output and original download
        for i, block in enumerate(splitter.blocks):
            actual_md5 = block.calc_md5(split_dir)
            split_md5 = block.md5
            orig_md5 = bd.blocks[i].md5

            print(f"Block {i:04d} offset={block.offset}:")
            print(f"  splitter md5 : {split_md5}")
            print(f"  original md5 : {orig_md5}")
            print(f"  actual   md5 : {actual_md5}")

            self.assertEqual(split_md5, actual_md5)
            self.assertEqual(orig_md5, actual_md5)
