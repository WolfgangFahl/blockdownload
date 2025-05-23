"""
Created on 2025-05-05

@author: wf
"""

import os

from bdown.block import StatusSymbol
from bdown.check import BlockCheck
from bdown.download import BlockDownload
from tests.baseblocktest import BaseBlockTest


class TestBlockCheck(BaseBlockTest):
    """
    Test the check module with cold-start support and no redundancy.
    """

    def setUp(self, debug=False, profile=True):
        super().setUp(debug, profile)

    def prepare_sample(self):
        """
        Ensure sample file and its YAML exist. Download and generate if needed.
        """
        os.makedirs(self.download_dir, exist_ok=True)

        if not os.path.exists(self.sample_path):
            block_download = BlockDownload(
                name=self.name,
                url=self.url,
                blocksize=self.blocksize,
                unit=self.unit,
            )
            block_download.download_via_os(self.sample_path)

        self.assertTrue(os.path.exists(self.sample_path), "Sample ISO must exist")

        if not os.path.exists(self.sample_path + ".yaml"):
            check = BlockCheck(
                name=self.name,
                file1=self.sample_path,
                blocksize=self.blocksize,
                unit=self.unit,
                head_only=True,
                create=True,
            )
            check.generate_yaml(self.url)

        self.assertTrue(os.path.exists(self.sample_path + ".yaml"), "YAML must exist")

    def test_blockcheck(self):
        """
        Test generation of YAML metadata for ISO
        """
        self.prepare_sample()
        self.assertEqual(self.sample_size, os.path.getsize(self.sample_path))

    def test_yaml_comparison(self):
        """
        Test comparing regenerated YAML with reference download YAML
        """
        self.prepare_sample()
        if not os.path.exists(self.yaml_path):
            self.fail(f"Missing download YAML at {self.yaml_path}")

        iso_yaml_path = self.sample_path + ".yaml"
        check_compare = BlockCheck(
            name=self.name,
            file1=self.yaml_path,
            file2=iso_yaml_path,
            blocksize=self.blocksize,
            unit=self.unit,
            head_only=True,
        )
        check_compare.compare()

        self.assertEqual(
            len(check_compare.status.symbol_blocks[StatusSymbol.FAIL]),
            0,
            "Found mismatched blocks"
        )
        self.assertTrue(check_compare.status.success)
