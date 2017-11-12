from .vault import VaultClient

class Cloud(object):
    """A single generic cloud provider. Meant to be subclassed. Examples:

    vault write /secret/landscape/clouds/staging-123456 provisioner=terraform
    vault write /secret/landscape/clouds/minikube provisioner=minikube

    Cloud attributes are read from Vault in a CloudCollection class,
    which are loaded into a provisioner-specific subclass

    Attributes:
        name: Name to uniquely identify the cloud.
        provisioner: Tool used to provision the cloud.
    """

    def __init__(self, name, dry_run=False, **kwargs):
        """Initializes a Cloud.

        Reads a cloud's definition from Vault.

        Args:
            name: the Cloud's unique name
            kwargs**:
              provisioner: The tool that provisioned the cloud
              git_branch: the git branch the cloud subscribes to

        Returns:
            None

        Raises:
            None
        """
        self.name = name
        self._DRYRUN = dry_run
        for key, value in kwargs.items():
          setattr(self, key, value)


    def __getitem__(self, x):
        """Enables the Cloud object to be subscriptable.

        Args:
            x: the element being subscripted.

        Returns:
            An arbitrary attribute of the class.

        Raises:
            None.
        """
        return getattr(self, x)


    def __str__(self):
        """Returns the cloud's name.

        Args:
            None.

        Returns:
            A String containing the cloud's unique name.

        Raises:
            None.
        """
        return self.name

