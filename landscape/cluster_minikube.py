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
        disable_addons = ['kube-dns', 'ingress']
        enable_addons = ['default-storageclass', 'registry-creds']

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
        self._configure_addon_registry_creds()


    def _configure_addon_registry_creds(self):
        """Configure minikube registry-creds addon for GCP use
        """
        gcr_creds_path = os.path.expanduser('~') + '/.config/gcloud/application_default_credentials.json'
        if not os.path.isfile(gcr_creds_path):
            raise EnvironmentError("GCP Application Default Credentials missing in {0}. Run `gcloud auth application-default login`".format(gcr_creds_path))
        child = pexpect.spawn('minikube addons configure registry-creds', encoding='utf-8')
        child.logfile = sys.stdout
        child.expect('Do you want to enable AWS Elastic Container Registry')
        child.sendline('n')
        child.expect('Do you want to enable Google Container Registry')
        child.sendline('y')
        child.expect('Enter path to credentials')
        child.sendline(gcr_creds_path)
        child.expect('Do you want to change the GCR URL')
        child.sendline('y')
        child.expect('Enter GCR URL')
        child.sendline('https://us.gcr.io')
        child.expect('Do you want to enable Docker Registry')
        child.sendline('n')
        child.expect('registry-creds was successfully configured')


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
