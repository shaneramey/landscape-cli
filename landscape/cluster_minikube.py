import subprocess
import logging
import pexpect
import os
import sys
import time

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
                logging.warn(
                    "Disabling addon with command: {0}".format(addon_cmd))
                check_cmd_failed = subprocess.call(addon_cmd, shell=True)
                if check_cmd_failed:
                    logging.warn(
                        'Failed to ' + \
                        "disable addon with command: {0}".format(addon_cmd))
            else:
                logging.info(
                    'DRYRUN: would be ' + \
                    "Disabling addon with command: {0}".format(addon_cmd))
        # addons to enable
        for enable_addon in enable_addons:
            addon_cmd = "minikube addons enable {0}".format(enable_addon)
            if not self._DRYRUN:
                logging.warn(
                    "Enabling addon with command: {0}".format(addon_cmd))
                check_cmd_failed = subprocess.call(addon_cmd, shell=True)
                if check_cmd_failed:
                    logging.warn(
                        'Failed to ' + \
                        "enable addon with command: {0}".format(addon_cmd))
            else:
                logging.info(
                    'DRYRUN: would be ' + \
                    "Enabling addon with command: {0}".format(addon_cmd))

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
        logging.info(
            "minikube cluster converge previously set current-context")

    def cluster_converge(self):
        """Performs post-provisioning initialization of minikube cluster

        Copies docker auth file from shared host filesystem to allow private 
        registry image pulling, as well as the usual (parent class) converge
        steps.

        Args:
            None.

        Returns:
            None.

        Raises:
            None.
        """
        sleep_after_localkube_restart_secs = 120

        docker_auth_file = '/var/lib/kubelet/config.json'
        auth_file_exists_cmd = 'minikube ssh ls ' + docker_auth_file
        if not self._DRYRUN:
            logging.info("Checking if docker auth is configured: {0}".format(
                auth_file_exists_cmd))
            proc = subprocess.Popen(
                auth_file_exists_cmd, stdout=subprocess.PIPE, shell=True)
            auth_file_name_match = proc.stdout.read().rstrip().decode()
            if auth_file_name_match != docker_auth_file:
                logging.info('Docker auth not configured on minikube VM. ' +
                             'Copying host docker auth file to minikube')
                logging.info('SSHing to minikube and copying docker auth ' +
                                'file /files/config.json to ' +
                                '/var/lib/kubelet/config.json, ' +
                                'restarting localkube, and ' +
                                "sleeping {0} seconds".format(
                                        sleep_after_localkube_restart_secs))
                # ssh into minikube and apply docker auth file from host
                # requires config.json from ~/.docker/ copied to
                # ~/.minikube/files/
                child = pexpect.spawn('minikube ssh', encoding='utf-8')
                child.logfile = sys.stdout
                child.expect('\$ ')
                child.sendline('sudo su -')
                child.expect('# ')
                child.sendline(
                    'cp /files/config.json /var/lib/kubelet/ && ' + \
                    'systemctl restart localkube --wait')
                child.expect('# ')
                child.sendline('exit')
                child.expect('\$ ')
                child.sendline('exit')
                child.expect(pexpect.EOF)
                child.wait()
                logging.info("Sleeping {0} seconds " \
                             "after localkube restart".format(
                    sleep_after_localkube_restart_secs))
                time.sleep(sleep_after_localkube_restart_secs)
            else:
                logging.info('Docker auth file already exists on minikube')
        # run generalized cluster converge steps after docker is auth'd
        # doing the above first (for example) allows Helm Tiller to use a
        #  private repository
        Cluster.cluster_converge(self)
