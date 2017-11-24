import subprocess
import logging
import pexpect
import os
import sys

from .cluster import Cluster

class MinikubeCluster(Cluster):
    """A Minikube-provisioned Kubernetes Cluster

    Secrets path must exist as:
    vault write /secret/landscape/clusters/minikube cloud_id=minikube
    vault write /secret/landscape/clouds/minikube provisioner=minikube

    Attributes:
        None.
    """
    
    def cluster_setup(self):
        """Converges minikube state and sets addons

        Checks if a minikube cloud is already running; initializes it if not

        Args:
            None.

        Returns:
            None.

        Raises:
            None.
        """

        logging.info('Configuring minikube addons')
        disable_addons = ['kube-dns', 'ingress', 'registry-creds']
        enable_addons = ['default-storageclass']

        # addons to disable
        for disable_addon in disable_addons:
            addon_cmd = "minikube addons disable {0}".format(disable_addon)
            if not self._DRYRUN:
                logging.warn("Disabling addon with command: {0}".format(addon_cmd))
                check_cmd_failed = subprocess.call(addon_cmd, shell=True)
                if check_cmd_failed:
                    logging.warn("Failed to disable addon with command: {0}".format(addon_cmd))
            else:
                logging.info("DRYRUN: would be Disabling addon with command: {0}".format(addon_cmd))
        # addons to enable
        for enable_addon in enable_addons:
            addon_cmd = "minikube addons enable {0}".format(enable_addon)
            if not self._DRYRUN:
                logging.warn("Enabling addon with command: {0}".format(addon_cmd))
                check_cmd_failed = subprocess.call(addon_cmd, shell=True)
                if check_cmd_failed:
                    logging.warn("Failed to enable addon with command: {0}".format(addon_cmd))
            else:
                logging.info("DRYRUN: would be Enabling addon with command: {0}".format(addon_cmd))


    def _configure_kubectl_credentials(self):
        """Don't configure kubectl for minikube clusters.

        Override parent class method to do nothing, because minikube sets up
        kubeconfig on its own

        Args:
            None.

        Returns:
            None.

        Raises:
            None.
        """
        logging.info("Using minikube's pre-configured KUBECONFIG entry")
        logging.info("minikube cluster converge previously set current-context")


    def cluster_converge(self):
        """Performs post-provisioning initialization of cluster

        Checks if Tiller is already installed. If not, install it.
        Sets up any additional clusterrolebindings wanted (in lieu of Helm)

        Args:
            None.

        Returns:
            None.

        Raises:
            None.
        """
        Cluster.cluster_converge(self)
        logging.info('SSHing to minikube and copying docker auth file /files/config.json to /var/lib/kubelet/config.json, and restarting localkube')

        child = pexpect.spawn('minikube ssh', encoding='utf-8')
        child.logfile = sys.stdout
        child.expect('\$ ')
        child.sendline('sudo su -')
        child.expect('# ')
        child.sendline('if [ ! -f /var/lib/kubelet/config.json ]; then cp /files/config.json /var/lib/kubelet/ && systemctl restart localkube --wait && sleep 30; fi')
        child.expect('# ')
        child.sendline('exit')
        child.expect('\$ ')
        child.sendline('exit')
        child.expect(pexpect.EOF)
