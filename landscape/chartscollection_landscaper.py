import os
import fnmatch
import yaml
import subprocess
import sys
import logging

from .vault import VaultClient
from .chartscollection import ChartsCollection
from .chart_landscaper import LandscaperChart
from .clustercollection import ClusterCollection

class LandscaperChartsCollection(ChartsCollection):
    """Loads up a directory of chart yaml for use by Landscaper

    vault write /secret/landscape/clouds/staging-123456 provisioner=terraform
    vault write /secret/landscape/clouds/minikube provisioner=minikube

    Attributes:
        kube_context: Kubernetes context for landscaper apply command
        charts: An integer count of the eggs we have laid.
        cluster_branch:  The branch of the landscaper repo that the cluster subscribes to
    """
    def __init__(self, path_to_repo, dry_run=False, **kwargs):
        """Initializes a set of charts for a cluster.

        Determines which yaml files in the directory structure should be applied
        based on cloud provisioner type and optionally a namespace selection.
        For example, minikube gets kube-dns but GKE (via terraform) does not.

        When namespaces=[], deploy all namespaces.

        Args:
            context_name: The Kubernetes context name in which to apply charts.
            namespace_selection: A List of namespaces for which to apply charts.

        Returns:
            None.

        Raises:
            None.
        """

        # Read charts from:
        #  - cluster's cloud type (minikube, terraform (GKE), unmanaged, etc.)
        #  - 'all' dir contains charts which can be applied to all clusters.
        # branch used to read landscaper secrets from Vault (to put in env vars)
        self._DRYRUN = dry_run
        self.context_name = kwargs['context_name']
        self.namespace_selection = kwargs['namespace_selection']
        self._charts = []
        if self.directory_on_proper_vault_branch(path_to_repo):
            self.workdir = path_to_repo
        else:
            raise ValueError('Landscaper dir not on Vault-specified branch')

        # self.cluster_branch = self.__get_landscaper_branch_that_cluster_subscribes_to()
        # self.charts = self.__load_landscaper_yaml_for_cloud_type_and_namespace_selection(namespace_selection)


    def directory_on_proper_vault_branch(self, repo_path):
        if self.git_branch_in_directory(repo_path) == self.charts_branch_name_for_cluster():
            return True
        else:
            return False


    def charts_branch_name_for_cluster(self):
        cluster = ClusterCollection.LoadClusterByName(self.context_name)
        return cluster.landscaper_branch


    def git_branch_in_directory(self, dir):
        """Gets the git branch of a specified directory

        Args: None

        Returns:
            git branch of specified directory (str)
        """
        git_branch_cmd = "git branch"
        logging.debug("Checking git branch in directory {0}".format(dir))
        logging.debug("Running {0}".format(git_branch_cmd))
        proc = subprocess.Popen(git_branch_cmd,
                                cwd=dir,
                                stdout=subprocess.PIPE,
                                shell=True)
        git_branch_cmd_output = proc.stdout.read().rstrip().decode()
        # wait for command return code
        proc.communicate()[0]
        if proc.returncode != 0:
            raise ChildProcessError('Could not detect git branch. Try passing --git-branch')

        git_branch_cmd_lines = git_branch_cmd_output.splitlines()
        starred_branchname = next((item for item in git_branch_cmd_lines if item.startswith('*')))
        current_branch = starred_branchname.strip()[2:]
        logging.info("Auto-detected branch to be: " + current_branch)

        return current_branch


    def __str__(self):
        """Pretty-prints a list of clusters

        Args:
            self: the current object

        Returns:
            A new-line separated str of charts in format:
            namespace/chart_name

        Raises:
            None.
        """
        output_lines = []
        for chart in self.list():
            output_lines.append(str(chart))

        return '\n'.join(output_lines)


    def list(self):
        """Lists charts"""
        return self.charts


    @property
    def git_branch(self):
        """Read landscaper branch for cluster name from vault

        Returns:
            landscaper branch for cluster, read from vault (str)
        """
        cluster = ClusterCollection.LoadClusterByName(self.context_name)
        return cluster.landscaper_branch


    @property
    def cloud_provisioner_for_cluster(self):
        """Read landscaper branch for cluster name from vault

        Returns:
            landscaper branch for cluster, read from vault (str)
        """
        cluster = ClusterCollection.LoadClusterByName(self.context_name)
        return cluster.cloud.provisioner


    @property
    def charts(self):
        """Loads Landscaper YAML files into a List if they are in namespaces
        
        Checks inside YAML file for namespace field and appends LandscaperChart
        to converge-charts list

        Args:
            None

        Returns:
            A list of LandscaperChart chart definitions.

        Raises:
            None.
        """
        landscaper_path = [self.workdir + '/' + s for s in self._chart_collections()]

        files = self._landscaper_filenames_in_dirs(landscaper_path)
        charts = []
        for landscaper_yaml in files:
            with open(landscaper_yaml) as f:
                chart_info = yaml.load(f)
                chart_namespace = chart_info['namespace']
                # load the chart if it matches a namespace selector list param
                # or if there's no namespace selector list, load all
                if chart_namespace in self.namespace_selection or not self.namespace_selection:
                    # Add path to landscaper yaml inside Chart object
                    chart_info['filepath'] = landscaper_yaml
                    chart = LandscaperChart(**chart_info)
                    charts.append(chart)
        return charts


    def _chart_collections(self):
        """Find out the cluster's cloud ID and what its provisioner is
            This is used to determine which charts to load
        """
        provisioner_specific_collection = self.cloud_provisioner_for_cluster
        collections = ['all'] + [provisioner_specific_collection]
        return collections

    def _landscaper_filenames_in_dirs(self, dirs_to_apply):
        """Generates a list of Landscaper files in specified directories

        Args:
            dirs_to_apply: List of paths to cluster-specific landscaper dirs

        Returns:
            A List of Landscaper files in the specified directories

        Raises:
            None.
        """
        landscaper_files = []
        for cloud_specific_charts_dir in dirs_to_apply:
            if cloud_specific_charts_dir in dirs_to_apply:
                for root, dirnames, filenames in os.walk(cloud_specific_charts_dir):
                    for filename in fnmatch.filter(filenames, '*.yaml'):
                        landscaper_files.append(os.path.join(root, filename))
        return landscaper_files


    def converge(self, dry_run):
        """Read namespaces from charts and apply them one namespace at a time.

        Performs steps:
         - for each namespace in self.charts
         - get secrets from Vault as environment variables
         - run landscaper apply
        """
        namespaces_to_apply = self.__namespaces()
        for namespace in namespaces_to_apply:
            envvar_secrets_for_namespace = self.get_landscaper_envvars_for_namespace(namespace)
            # Get list of yaml files
            yamlfiles_in_namespace = [item.filepath for item in self.charts if item.namespace == namespace]
            self.deploy_charts_for_namespace(yamlfiles_in_namespace, namespace, envvar_secrets_for_namespace)


    def __namespaces(self):
        """Returns a list of namespaces defined in all charts for provisioner
           This means all namespaces in 1 of minikube, terraform, or unmanaged
        """
        PRIORTY_NAMESPACES = [
            'auto-approve-csrs',
            'kube-system',
        ]
        sorted_namespaces = []
        nsdict = {}
        all_provisioner_charts = self.charts
        # Generate namespace list by reading every chart's value
        for chart in all_provisioner_charts:
            candidate_ns = getattr(chart, 'namespace')
            if not candidate_ns in nsdict:
                nsdict[candidate_ns] = 1

        # install the high-priority namespaces first
        for priority_namespace in PRIORTY_NAMESPACES:
            if priority_namespace in nsdict:
                sorted_namespaces.append(priority_namespace)

        # install other namespaces
        for normal_namespace in nsdict.keys():
            if not normal_namespace in PRIORTY_NAMESPACES:
                sorted_namespaces.append(normal_namespace)

        return sorted_namespaces


    def get_landscaper_envvars_for_namespace(self, namespace):
        # pull secrets from Vault and apply them as env vars
        secrets_env = {}
        for chart_release_definition in self.charts:
            if chart_release_definition.namespace == namespace and chart_release_definition.secrets:
                chart_secrets_envvars = self.vault_secrets_for_chart(
                                            chart_release_definition.namespace,
                                            chart_release_definition.name)

                # Check if this chart's secrets would conflict with existing
                # environment variables. Update the env vars with them, if not.
                # Generate error message if key already exists.
                for envvar_key, envvar_val in chart_secrets_envvars.items():
                    if envvar_key not in secrets_env:
                        secrets_env[envvar_key] = envvar_val
                    else:
                        raise ValueError("Environment variable {0} already set in environment! Aborting.")

                # check each landscaper yaml secret to make sure it's been pulled
                # from Vault.
                # Build a list of missing secrets
                vault_missing_secrets = []
                for landscaper_secret in chart_release_definition.secrets:
                    # Generate error message if secret(s) missing
                    if landscaper_secret not in secrets_env:
                        vault_missing_secrets.append(landscaper_secret)
                # Report on any missing secrets
                if vault_missing_secrets:
                    for missing_secret in vault_missing_secrets:
                        logging.error('Missing landscaper secret ' + missing_secret)
                    sys.exit(1)

        landscaper_env_vars = self.vault_secrets_to_envvars(secrets_env)
        return landscaper_env_vars


    def deploy_charts_for_namespace(self, landscaper_filepaths, k8s_namespace, envvars):
        """Pulls secrets from Vault and converges charts using Landscaper.

        Helm Tiller must already be installed. Injects environment variables 
        pulled from Vault into local environment variables, so landscaper can
        apply the secrets from Vault.

        Args:
            dry_run: flag for simulating convergence

        Returns:
            None.

        Raises:
            None.
        """
        # list of landscape yaml files to apply
        # Build up a list of namespaces to apply, and deploy them
        # Note: Deploying a single chart is not possible when more than 2
        #       at in a namespace. This is because Landscaper wipes the ns 1st 
        ls_apply_cmd = 'landscaper apply -v --namespace=' + \
                            k8s_namespace + \
                            ' --context=' + self.context_name + \
                            ' ' + ' '.join(landscaper_filepaths)
        if self._DRYRUN:
            ls_apply_cmd += ' --dry-run'
        logging.info('Executing: ' + ls_apply_cmd)
        # update env to preserve VAULT_ env vars
        os.environ.update(envvars)
        create_failed = subprocess.call(ls_apply_cmd, shell=True)
        if create_failed:
            sys.exit("ERROR: non-zero retval for {}".format(ls_apply_cmd))


    def vault_secrets_for_chart(self, chart_namespace, chart_name):
        """Read Vault secrets for a deployment (chart name + namespace).

        Args:
            chart_namespace: The namespace where the chart will be installed.
            chart_name: The name of the chart being installed.

        Returns:
            A dict of Vault secrets, pulled from a deployment-specific key

        Raises:
            None.
        """
        chart_vault_secret = "/secret/landscape/charts/{0}/{1}/{2}".format(
                                                    self.git_branch,
                                                    chart_namespace,
                                                    chart_name
                                                   )
        logging.info("Reading path {0}".format(chart_vault_secret))
        vault_secrets = VaultClient().dump_vault_from_prefix(chart_vault_secret, strip_root_key=True)
        return vault_secrets


    def vault_secrets_to_envvars(self, vault_secrets):
        """Converts secrets pulled from Vault to environment variables.

        Used by Landscaper to inject environment variables into secrets.

        Args:
            vault_secrets: A dict of secrets, typically pulled from Vault.

        Returns:
            A dict of secrets, converted to landscaper-compatible environment
            variables.

        Raises:
            None.
        """
        envvar_list = {}
        for secret_key, secret_value in vault_secrets.items():
            envvar_key = self.helm_secret_name_to_envvar_name(secret_key)
            envvar_list.update({envvar_key: secret_value})
        return envvar_list


    def helm_secret_name_to_envvar_name(self, keyname):
        """Translate helm secret name to environment variable.

        The environment variable is then read by the landscaper command

        e.g., secret-admin-password becomes SECRET_ADMIN_PASSWORD

        Args:
            keyname: A String of the environment variable name.

        Returns:
            A String converted to capitalized environment variable.

        Raises:
            None.
        """
        return keyname.replace('-', '_').upper()
