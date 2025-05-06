"""
Created on 2025-05-05

@author: wf
"""

from bdown.check import BlockCheck
from tests.basetest import BaseTest


class TestBlockCheck(BaseTest):
    """
    test the check module
    """

    def setUp(self, debug=False, profile=True):
        super().setUp(debug, profile)

    def test_blockcheck(self):
        """
        test a blockcheck
        """
