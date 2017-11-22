import logging

from .vault import VaultClient
from .cloud import Cloud
from .cloud_minikube import MinikubeCloud
from .cloud_terraform import TerraformCloud
from .cloud_unmanaged import UnmanagedCloud


class CloudCollection(object):
    """A group of clouds.

    Generates a list of clouds. Cluster type is determined by its Cloud's
    "provisioner" attribute. Each cloud behaves differently
    (i.e., provision VMs) based on its type

    Attributes:
        clouds: (optionally) filtered list of clouds, read from Vault
    """

    vault_prefix = '/secret/landscape/clouds'

    @classmethod
    def LoadCloudByName(cls, cloud_name, terraform_dir='.'):
        cloud_vault_path = CloudCollection.vault_prefix + '/' + cloud_name
        cloud_parameters = VaultClient().dump_vault_from_prefix(
                            cloud_vault_path, strip_root_key=True)
        if cloud_parameters['provisioner'] == 'minikube':
            cloud_from_vault = MinikubeCloud(cloud_name, **cloud_parameters)
            return(cloud_from_vault)
        elif cloud_parameters['provisioner'] == 'terraform':
            cloud_parameters.update({ 'path_to_terraform_repo': terraform_dir })
            cloud_from_vault = TerraformCloud(cloud_name, **cloud_parameters)
            return(cloud_from_vault)
        elif cloud_parameters['provisioner'] == 'unmanaged':
            cloud_from_vault = UnmanagedCloud(cloud_name, **cloud_parameters)
            return(cloud_from_vault)
        else:
            raise ValueError("Bad Provisioner: {0}".format(cloud_provisioner))


    def __init__(self, **kwargs):
        """initializes a CloudCollection for a given git branch.

        Reads a dict of clouds from Vault, and filter the results based on the
        git branch passed into the constructor.

        Args:
            git_branch_selector(str): If set, CloudCollection is
                composed of only clouds subscribed to this branch. Set in
                Vault-defined settings for the cloud

        Returns:
            None.

        Raises:
            None.
        """

        self.git_branch_selector = kwargs['git_branch']
        self.path_to = kwargs['git_branch']
        self._clouds = []


    def __str__(self):
        """Pretty-prints a list of clouds

        Args:
            self: the current object

        Returns:
            A new-line separated str of cloud names

        Raises:
            None.
        """
        cloud_names = []
        for cloud in self.clouds:
            cloud_names.append(cloud.name)
        return '\n'.join(cloud_names)


    def __getitem__(self, cloud_name):
        """returns a Cloud with a given name.

        Used to iterate and index clouds

        Args:
            cloud_name: index for the cloud within self.clusters

        Returns:
            A single Cloud object named cloud_name.

        Raises:
            None.
        """
        logging.debug("cloud_name is".format(cloud_name))
        logging.debug("clouds are".format(self.clouds))
        cloud = next((item for item in self.clouds if item.name == cloud_name))
        return cloud


    @property
    def clouds(self):
        """Loads clouds from Vault and filters them
        """
        if not self._clouds:
            clouds_in_vault = VaultClient().dump_vault_from_prefix(
                CloudCollection.vault_prefix, strip_root_key=True)
            for cloud_name, cloud_attribs in clouds_in_vault.items():
                if self.valid_cloud_attribs_for_selection(cloud_attribs):
                    loaded_cloud = CloudCollection.LoadCloudByName(cloud_name)
                    self._clouds.append(loaded_cloud)
        return self._clouds


    def valid_cloud_attribs_for_selection(self, attribs):
        if self.git_branch_selector:
            if attribs['provisioner_branch'] != self.git_branch_selector:
                return False
        return True


    def __load_clouds_from_vault(self):
        """Retrieves cloud definitions from Vault and loads them into a dict

        Args:
            None.

        Returns:
            A dict mapping keys to the corresponding table row data
            fetched. Each row is represented as a tuple of strings. For
            example:

            {
                'staging-123456': <TerraformCloud>,
                'minikube': <MinikubeCloud>
            }

        Raises:
            None.
        """
        # Dump Vault
        cloud_defs = VaultClient().dump_vault_from_prefix(
            CloudCollection.vault_prefix, strip_root_key=True)
        # add name into object
        clouds = []
        for cloud_name in cloud_defs:
            print("cloud_name={0}".format(cloud_name))
            cloud = CloudCollection.LoadCloudByName(cloud_name)
            clouds.append(cloud)
        return clouds


    def list(self):
        """Retrieves all clouds from Vault

        Args:
            None.

        Returns:
            A dict of clouds, having their unique identifier as a key
            fetched. Each row is represented as a tuple of strings. For
            example:

            {'minikube': <MinikubeCloud>}

        Raises:
            ValueError: if Vault doesn't understand the cloud provisioner
        """

        return self.clouds
