import logging
import subprocess
import os
from .kubernetes import kubectl_use_context
from .helm import wait_for_tiller_ready
from .vault import VaultClient
from .cloudcollection import CloudCollection

class Cluster(object):
    """A single generic Kubernetes cluster. Meant to be subclassed.

    Should include methods to initialize a kubernetes cluster and install helm.

    Attributes:
        name: the name of the cluster
        cloud_id: the cloud that provisioned the cluster's ID

    """
    def __init__(self, name, dry_run=False, **kwargs):
        """initializes a Cluster.

        Reads a cluster's definition from Vault.

        Args:
            kwargs**:
              context_id: the Cluster's context name on local machine
              cloud_id: a list of Clouds, one of which should (if defined
              in Vault properly) host the Cluster

        Returns:
            None

        Raises:
            None
        """
        self.name = name
        self._DRYRUN = dry_run
        for key, value in kwargs.items():
            setattr(self, key, value)
            # split up landscaper_namespaces CSV from Vault into list
            if key == 'landscaper_namespaces':
                self.namespace_subscriptions = value.split(',')

    @property
    def cloud(self):
        cloud_id = self.cloud_id
        return CloudCollection.LoadCloudByName(cloud_id)

    def converge(self):
        """Stages of a Kubernetes Cluster converge.
        """
        self.apply_tiller()


    def setup_tiller_clusterrole_and_serviceaccount(self):
        """Provisions necessary Tiller RBAC role
        """
        self.create_serviceaccount('tiller', 'kube-system')
        self.create_clusterrolebinding('tiller', 'kube-system', 'cluster-admin')



    def apply_tiller(self):
        """Checks if Tiller is already installed. If not, install it.

        Retrieves rows pertaining to the given keys from the Table instance
        represented by big_table.  Silly things may happen if
        other_silly_variable is not None.

        Args:
            None.

        Returns:
            None.

        Raises:
            None.
        """
        tiller_pod_status_cmd = 'kubectl get pod --context=' + self.name + \
                                ' --namespace=kube-system ' + \
                                '-l app=helm -l name=tiller ' + \
                                '-o jsonpath=\'{.items[0].status.phase}\''

        if not self._DRYRUN:
            logging.info('Checking tiller pod status with command: ' + \
                            tiller_pod_status_cmd)
            DEVNULL = open(os.devnull, 'w')
            proc = subprocess.Popen(tiller_pod_status_cmd,
                                    stdout=subprocess.PIPE,
                                    stderr=DEVNULL, shell=True)

            tiller_pod_status = proc.stdout.read().rstrip().decode()
            # if Tiller isn't initialized, wait for it to come up
            if not tiller_pod_status == "Running":
                logging.info('Did not detect tiller pod')
                self.init_tiller()
            else:
                logging.info('Detected running tiller pod')
            # make sure Tiller is ready to accept connections
            wait_for_tiller_ready(tiller_pod_status_cmd)
        else:
            logging.info('DRYRUN: would be Checking tiller pod status with command: ' + \
                            tiller_pod_status_cmd)


    def init_tiller(self):
        """Creates Tiller RBAC permissions and initializes Tiller.

        Retrieves rows pertaining to the given keys from the Table instance
        represented by big_table.  Silly things may happen if
        other_silly_variable is not None.

        Args:
            None.

        Returns:
            None.

        Raises:
            None.
        """
        # Set up Tiller serviceaccount and clusterrolebinding
        self.setup_tiller_clusterrole_and_serviceaccount()

        # Initialize Helm by installing Tiller
        helm_provision_cmd = "helm init --service-account=tiller " + \
                             "--kube-context={0}".format(self.name)
        if not self._DRYRUN:
            logging.info('Initializing Tiller: ' + \
                            helm_provision_cmd)
            subprocess.call(helm_provision_cmd, shell=True)
        else:
            logging.info('DRYRUN: would be Initializing Tiller: ' + \
                    helm_provision_cmd)

        # Minikube:
        if self.name == "minikube":
            #system:serviceaccount:kube-system:default
            pass


    def create_extra_accts(self):
        # needed until minikube includes a kubernetes-dashboard
        # clusterrolebinding, or this is put into a helm chart
        SA_CRB_MAPPING = [
            {
                'id': 'default',
                'namespace': 'kube-system',
                'clusterrole': 'cluster-admin',
            }
        ]
        
        for acct in SA_CRB_MAPPING:
            name = acct['id']
            ns = acct['namespace']
            cr = acct['clusterrole']
            self.create_serviceaccount(name, ns)
            self.create_clusterrolebinding(name, ns, cr)


    def create_serviceaccount(self, sa_name, namespace):
        # Create ServiceAccount
        sa_create_cmd = 'kubectl create serviceaccount ' + sa_name + \
                        ' --context=' + self.name + \
                        ' --namespace=' + namespace
        if not self._DRYRUN:
            logging.info('Creating serviceaccount: ' + sa_create_cmd)
            subprocess.call(sa_create_cmd, shell=True)
        else:
            logging.info('DRYRUN: would be Creating serviceaccount: ' + \
                    sa_create_cmd)


    def create_clusterrolebinding(self, sa_name, namespace, clusterrole):
        # Create ClusterRoleBinding with cluster-admin role
        crb_create_cmd = 'kubectl create clusterrolebinding ' + \
                            'landscape-' + sa_name + \
                            ' --context=' + self.name + \
                            ' --clusterrole=' + clusterrole + \
                            ' --serviceaccount=' + namespace + ':' + sa_name
        if not self._DRYRUN:
            logging.info('Creating ClusterRoleBinding: ' + crb_create_cmd)
            subprocess.call(crb_create_cmd, shell=True)
        else:
            logging.info('DRYRUN: would be Creating ClusterRoleBinding: ' + \
                crb_create_cmd)
