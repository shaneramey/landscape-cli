import logging

from .vault import VaultClient
from .cloud import Cloud
from .cluster_minikube import MinikubeCluster
from .cluster_terraform import TerraformCluster
from .cluster_unmanaged import UnmanagedCluster
from .cloudcollection import CloudCollection # for linking a cluster to a cloud


class ClusterCollection(object):
    """A group of clusters.

    Generates a list of clusters. Cluster type is determined by its Cloud's
    "provisioner" attribute. Each cluster behaves differently (i.e., which
    chart directories to deploy, what the converge steps are) based on its type

    Attributes:
        clusters: (optionally) filtered list of clusters, read from Vault
    """

    vault_prefix = '/secret/landscape/clusters'

    @classmethod
    def LoadClusterByName(cls, cluster_name):
        cluster_vault_path = ClusterCollection.vault_prefix + '/' + cluster_name
        cluster_parameters = VaultClient().dump_vault_from_prefix(
                                cluster_vault_path, strip_root_key=True)

        retval = None
        cloud_id_for_cluster = cluster_parameters['cloud_id']
        cluster_cloud = CloudCollection.LoadCloudByName(cloud_id_for_cluster)
        # Assume the cluster was provisioned inside of the cloud
        # Then, their provisioners are the same
        cc_provisioner = cluster_cloud.provisioner

        if cc_provisioner == 'minikube':
            retval = MinikubeCluster(cluster_name, **cluster_parameters)
        elif cc_provisioner == 'terraform':
            retval = TerraformCluster(cluster_name, **cluster_parameters)
        elif cc_provisioner == 'unmanaged':
            retval = UnmanagedCluster(cluster_name, **cluster_parameters)
        else:
            raise ValueError("Bad Provisioner: {0}".format(cc_provisioner))
        return(retval)


    def __init__(self, **kwargs):
        """initializes a ClusterCollection for a given git branch.

        Reads a dict of clusters from Vault, and filter the results based on the
        git branch passed into the constructor.

        Args:
            cloud_collection(List): Clouds that contain the cluster(s). Used to
                identify the cluster's type
            cloud_selector(str): If set, ClusterCollection is composed of only
                clusters in this cloud
            git_branch_selector(str): If set, ClusterCollection is
                composed of only clusters subscribed to this branch. Set in
                Vault-defined settings for the cluster

        Returns:
            None.

        Raises:
            None.
        """
        self.cloud_selector = kwargs['cloud']
        self.git_branch_selector = kwargs['git_branch']

        self._clusters = []


    @property
    def clusters(self):
        """Loads clusters from Vault and filters them
        """
        if not self._clusters:
            clusters_in_vault = VaultClient().dump_vault_from_prefix(
                        ClusterCollection.vault_prefix, strip_root_key=True)
            for cluster_name, cluster_attribs in clusters_in_vault.items():
                # If git_branch_selector is None, generate collection of
                # all clusters. Otherwise, generate collection including only
                # clusters subscribing to this branch.
                if self.valid_cluster_attribs_for_selection(cluster_attribs):
                    loaded_cluster = ClusterCollection.LoadClusterByName(cluster_name)
                    self._clusters.append(loaded_cluster)
        return self._clusters


    def valid_cluster_attribs_for_selection(self, attribs):
        if self.valid_cluster_branch_for_selection(attribs) and \
            self.valid_cloud_id_for_selection(attribs):
            return True
        else:
            return False

    def valid_cluster_branch_for_selection(self, attribs):
        if self.git_branch_selector:
            if attribs['landscaper_branch'] != self.git_branch_selector:
                return False
        return True


    def valid_cloud_id_for_selection(self, attribs):
        if self.cloud_selector:
            if attribs['cloud_id'] != self.cloud_selector:
                return False
        return True


# cloud_selection, charts_branch_selection

    def __str__(self):
        """Pretty-prints a list of clusters

        Args:
            self: the current object

        Returns:
            A new-line separated str of cluster names

        Raises:
            None.
        """
        cluster_names = []
        for cluster in self.clusters:
            cluster_names.append(cluster.name)
        return '\n'.join(cluster_names)


    def __getitem__(self, cluster_name):
        """returns a Cluster with a given name

        Args:
            cluster_name: index for the cluster within self.clusters

        Returns:
            A single Cluster object named cluster_name.

        Raises:
            None.
        """
        logging.debug("cluster_name is".format(cluster_name))
        logging.debug("clusters are".format(self.clusters))
        cluster = next((item for item in self.clusters if item.name == cluster_name))
        return cluster


    def list(self):
        """Generates list of clusters and returns them.

        Args:
            None

        Returns:
            a dict of clusters that may have been filtered from a larger dict.
            For example:

            {
                'gke_staging-123456-west1-a_master': <TerraformCluster>,
                'minikube': <MinikubeCluster>
            }


        Raises:
            None.
        """

        return self.clusters
