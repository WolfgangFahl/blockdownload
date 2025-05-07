"""
Created on 2025-05-05

@author: wf
"""

from bdown.check import BlockCheck
from bdown.download import BlockDownload
from tests.baseblocktest import BaseBlockTest
import os

class TestBlockCheck(BaseBlockTest):
    """
    test the check module
    """

    def setUp(self, debug=False, profile=True):
        super().setUp(debug, profile)
        self.iso_file_name="debian-12.10.0-amd64-netinst.iso"
        self.iso_path = os.path.join(self.download_dir, self.iso_file_name)

    def test_blockcheck(self):
        """
        test a blockcheck
        """
        if os.path.exists(self.yaml_path):
            block_download = BlockDownload.load_from_yaml_file(self.yaml_path)
        iso_exists = os.path.exists(self.iso_path)
        if self.inPublicCI() or self.inLocalCI() and not iso_exists:
            self.iso_size=block_download.download_via_os(self.iso_path)
        else:
            self.iso_size=os.path.getsize(self.iso_path)
        self.assertEqual(663748608,self.iso_size)
        # Generate YAML if needed for the ISO file
        iso_yaml_path = self.iso_path + ".yaml"
        if not os.path.exists(iso_yaml_path):
            # Test YAML generation
            check = BlockCheck(
                file1=self.iso_path,
                blocksize=self.blocksize,
                unit=self.unit,
                head_only=True,
                create=True
            )
            check.generate_yaml()
            self.assertTrue(os.path.exists(iso_yaml_path), "YAML file should be created")
