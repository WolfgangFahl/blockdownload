"""
Created on 07.05.2025

@author: wf
"""

"""
Created on 2025-05-07

@author: wf
"""

import os
from datetime import datetime

from tests.basetest import BaseTest


class BaseBlockTest(BaseTest):
    """
    Base class for testing block operations
    """

    def setUp(self, debug=False, profile=True):
        BaseTest.setUp(self, debug=debug, profile=profile)
        iso_date = datetime.now().strftime("%Y-%m-%d")
        self.name = "debian12"
        self.download_dir = os.path.join(os.path.expanduser("~"), self.name, iso_date)
        os.makedirs(self.download_dir, exist_ok=True)
        self.yaml_path = os.path.join(self.download_dir, f"{self.name}.yaml")
        self.url = "https://cdimage.debian.org/debian-cd/current/amd64/iso-cd/debian-12.10.0-amd64-netinst.iso"
        self.blocksize = 32
        self.unit = "MB"
