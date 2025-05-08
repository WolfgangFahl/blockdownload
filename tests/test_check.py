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
    test the check module
    """

    def setUp(self, debug=False, profile=True):
        super().setUp(debug, profile)
        self.iso_file_name = "debian-12.10.0-amd64-netinst.iso"
        self.iso_path = os.path.join(self.download_dir, self.iso_file_name)

    def get_block_download(self) -> BlockDownload:
        if os.path.exists(self.yaml_path):
            block_download = BlockDownload.load_from_yaml_file(self.yaml_path)
        return block_download

    def test_blockcheck(self):
        """
        test a blockcheck
        """
        iso_exists = os.path.exists(self.iso_path)
        # if self.inPublicCI() or self.inLocalCI() and
        if not iso_exists:
            block_download = self.get_block_download()
            self.iso_size = block_download.download_via_os(self.iso_path)
        else:
            self.iso_size = os.path.getsize(self.iso_path)
        self.assertEqual(663748608, self.iso_size)
        # Generate YAML if needed for the ISO file
        iso_yaml_path = self.iso_path + ".yaml"
        if not os.path.exists(iso_yaml_path):
            # Test YAML generation
            check = BlockCheck(
                name=self.name,
                file1=self.iso_path,
                blocksize=self.blocksize,
                unit=self.unit,
                head_only=True,
                create=True,
            )
            check.generate_yaml(self.url)
            self.assertTrue(
                os.path.exists(iso_yaml_path), "YAML file should be created"
            )

    def test_yaml_comparison(self):
        """
        Test comparing a download YAML with a directly created YAML
        """
        iso_yaml_path = self.iso_path + ".yaml"
        if not os.path.exists(iso_yaml_path):
            self.fail(f"missing {iso_yaml_path}")

        check_compare = BlockCheck(
            name=self.name,
            file1=self.yaml_path,  # The download YAML
            file2=iso_yaml_path,  # The direct YAML
            blocksize=self.blocksize,
            unit=self.unit,
            head_only=True,
        )
        check_compare.compare()

        # The comparison should show all blocks matching
        num_fails = len(check_compare.status.symbol_blocks[StatusSymbol.FAIL])
        self.assertEqual(num_fails, 0, f"Found {num_fails} mismatched blocks")
        self.assertTrue(check_compare.status.success)
