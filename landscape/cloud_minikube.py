import subprocess
import sys
import logging
import shutil
from os.path import expanduser

from .cloud import Cloud

class MinikubeCloud(Cloud):
    """A Minikube-provisioned Virtual Machine

    Secrets path must exist as:
    vault write /secret/landscape/clouds/minikube provisioner=minikube

    Attributes:
        Inherited from superclass.
    """

    def converge(self, dry_run):
        """Converges state of a minikube VM

        Checks if a minikube cloud is already running
        Initializes it if not yet running

        Args:
            None.

        Returns:
            None.

        Raises:
            None.
        """
        status_cmd = 'minikube status --format=\'{{.MinikubeStatus}}\''
        proc = subprocess.Popen(status_cmd, stdout=subprocess.PIPE, shell=True)
        cloud_status = proc.stdout.read().rstrip().decode()
        logging.debug('Minikube Cloud status is ' + cloud_status)
        if cloud_status == 'Running':
            if not dry_run:
                logging.info('Re-using previously provisioned cloud')
            else:
                logging.info('DRYRUN: would be Re-using previously ' + \
                                'provisioned cloud')
        else:
            logging.info('Initializing Cloud')
            if not dry_run:
                self.initialize_cloud()
            else:
                logging.info('DRYRUN: would be Initializing Cloud')


    def initialize_cloud(self):
        """Start minikube.

        Args:
            None.

        Returns:
            None.

        Raises:
            None.
        """

        # Copy docker registry credentials to inside minikube
        home = expanduser('~')
        docker_local_auth_file = home + '/.docker/config.json'
        minikube_file_copy_location = home + '/.minikube/files/'
        inside_minikube_docker_auth_file = '/files/config.json'
        logging.info("Copying file: {0} from local machine to inside " + \
                        "minikube VM at path: {1} via path: {2}".format(
                            docker_local_auth_file,
                            inside_minikube_docker_auth_file,
                            minikube_file_copy_location))
        shutil.copy(docker_local_auth_file, minikube_file_copy_location)

        # start minikube
        start_cmd_tmpl = 'minikube start ' + \
                '--kubernetes-version=v{0} ' + \
                "--vm-driver={1} " + \
                "--dns-domain={2} " + \
                '--extra-config=apiserver.Authorization.Mode=RBAC ' + \
                '--extra-config=controller-manager.ClusterSigningCertFile=' + \
                '/var/lib/localkube/certs/ca.crt ' + \
                '--extra-config=controller-manager.ClusterSigningKeyFile=' + \
                '/var/lib/localkube/certs/ca.key ' + \
                '--cpus=8 ' + \
                '--disk-size=40g ' + \
                '--memory=8192 ' + \
                '--docker-env HTTPS_PROXY=$http_proxy ' + \
                '--docker-env HTTP_PROXY=$https_proxy ' + \
                '--keep-context ' + \
                '-v=2'
        start_cmd = start_cmd_tmpl.format('1.8.0',
                                            'xhyve',
                                            'cluster.local')
        logging.info("Starting minikube with command: {0}".format(start_cmd))
        minikube_start_failed = subprocess.call(start_cmd, shell=True)
        if minikube_start_failed:
            sys.exit('ERROR: minikube cloud initialization failure')
        self.set_minikube_clock()


    def set_minikube_clock(self):
        """Workaround for https://github.com/kubernetes/minikube/issues/1378
        """
        cmd = 'minikube ssh -- docker run -i --rm --privileged --pid=host debian nsenter -t 1 -m -u -n -i date -u $(date -u +%m%d%H%M%Y)'
        cmd_failed = subprocess.call(cmd, shell=True)
        if cmd_failed:
            sys.exit('ERROR: could not set clock of minikube')
        else:
            logging.info('Set minikube clock successfully')
