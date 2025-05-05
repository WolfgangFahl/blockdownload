"""
Created on 2025-05-05

@author: wf
"""

import os
from datetime import datetime
from bdown.download import BlockDownload
from tests.basetest import BaseTest


class TestBlockDownload(BaseTest):
    """
    Test the segmented download using HTTP range requests.
    """

    def setUp(self, debug=False, profile=True):
        super().setUp(debug, profile)
        iso_date = datetime.now().strftime("%Y-%m-%d")
        self.download_dir = os.path.join(os.path.expanduser("~"), "blazegraph", iso_date)
        os.makedirs(self.download_dir, exist_ok=True)
        self.yaml_path = os.path.join(self.download_dir, "blazegraph.yaml")

    def test_blockdownload(self):
        """
        Download file in 10MB segments and save to individual files named by block index.
        Recalculate and compare the MD5 checksums of the downloaded blocks.
        """
        if os.path.exists(self.yaml_path):
            block_download = BlockDownload.load_from_yaml_file(self.yaml_path)
        else:
            block_download = BlockDownload(
                url="https://datasets.orbopengraph.com/blazegraph/data.jnl",
                blocksize=10,
                unit="MB"
            )

        block_download.download(self.download_dir, 0, 5)

        for i, block in enumerate(block_download.blocks):
            actual_md5 = block.calc_md5(self.download_dir)
            stored_md5 = block.md5 or "(not set)"
            print(f"Block {i:04d} offset={block.offset}:")
            print(f"  stored md5 : {stored_md5}")
            print(f"  actual md5 : {actual_md5}")

