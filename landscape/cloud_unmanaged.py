import subprocess
import sys
import logging

from .cloud import Cloud

class UnmanagedCloud(Cloud):
    """
    Represents a Cloud provisioned outside of this tool
    """

    def converge(self):
        """Override this method in your subclass.

        Args:
            None.

        Returns:
            None.

        Raises:
            NotImplementedError if called directly.
        """
        if self._DRYRUN:
            logging.info('DRYRUN: UnmanagedClouds do not converge')
        else:
            logging.info('UnmanagedClouds do not converge')

