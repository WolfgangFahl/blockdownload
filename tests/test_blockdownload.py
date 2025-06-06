"""
Created on 2025-05-05

@author: wf
"""

import os

from bdown.download import BlockDownload
from tests.baseblocktest import BaseBlockTest


class TestBlockDownload(BaseBlockTest):
    """
    Test the segmented download using HTTP range requests.
    """

    @classmethod
    def setUpClass(cls)->None:
        super(TestBlockDownload, cls).setUpClass()
        cls.downloaded=False

    def setUp(self, debug=True, profile=True):
        super().setUp(debug, profile)


    def test_blockdownload(self):
        """
        We will test downloading a Debian iso image
        from https://cdimage.debian.org/debian-cd/current/amd64/iso-cd/

        Download file in 512KB segments and save to individual files named by block index.
        Recalculate and compare the MD5 checksums of the downloaded blocks.
        """
        if TestBlockDownload.downloaded:
            return
        from_block = 0
        if self.inLocalCI() or self.inPublicCI():
            to_block = None
            block_size = 32
            unit = "MB"
        else:
            to_block = 3
            block_size = 512
            unit = "KB"
            to_block = None
            block_size = 32
            unit = "MB"
        if os.path.exists(self.yaml_path):
            block_download = BlockDownload.load_from_yaml_file(self.yaml_path) # @UndefinedVariable
        else:
            block_download = BlockDownload(
                name=self.name,
                url=self.url,
                blocksize=block_size,
                unit=unit,
            )
            block_download.yaml_path = self.yaml_path
        block_download.compute_total_bytes(from_block, to_block)
        if self.debug:
            progress_bar = block_download.get_progress_bar(from_block, to_block)
            progress_bar.set_description("Downloading")
            with progress_bar:
                block_download.download(
                    self.download_dir, from_block, to_block, progress_bar=progress_bar,force=True
                )
        else:
            block_download.download(self.download_dir, from_block, to_block,force=True)

        block_download.save()
        for i, block in enumerate(block_download.blocks):
            actual_md5 = block.calc_md5(self.download_dir)
            stored_md5 = block.md5 or "(not set)"
            print(f"Block {i:04d} offset={block.offset}:")
            print(f"  stored md5 : {stored_md5}")
            print(f"  actual md5 : {actual_md5}")
        TestBlockDownload.downloaded=True

    def test_reassemble(self):
        """Test reassembling blocks into complete file and verify MD5"""
        # First ensure blocks are downloaded
        self.test_blockdownload()

        # Load the BlockDownload instance
        block_download = BlockDownload.ofYamlPath(self.yaml_path)

        # Reassemble the file
        output_file = os.path.join(self.download_dir, f"{self.name}.iso")
        calculated_md5 = block_download.reassemble(
            parts_dir=self.download_dir,
            output_path=output_file,
            force=True
        )

        # Verify file exists and MD5 matches
        self.assertTrue(os.path.exists(output_file))
        self.assertEqual(calculated_md5, "113c231b4fb992c3e563a3206e6447bb")

        print(f"Reassembled file MD5: {calculated_md5}")
