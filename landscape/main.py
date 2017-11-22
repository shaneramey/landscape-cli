#! /usr/bin/env python3

"""
Usage: landscape [options]
        cloud (list [--git-branch=<git_branch> | --all-branches] [--cluster=<cluster_name>] | 
               converge [--cloud=<cloud_project>] [--landscaper-dir=<landscaper_yaml_path>])
       landscape [options]
        cluster [--cluster=<cluster_name>] [--cloud=<cloud_name>] (list 
         [--git-branch=<git_branch> | --all-branches] |
         converge [--converge-cloud])
       landscape [options]
        charts --cluster=<cluster_name> [--namespaces=<namespaces>] [--landscaper-dir=<landscaper_yaml_path>]
          (list [--namespaces=<namespaces>] [--git-branch=<git_branch>]
         | converge [--namespaces=<namespaces>] [--converge-cluster] [--converge-cloud] [--converge-localmachine])
       landscape [options]
        secrets overwrite-vault-with-lastpass 
         --secrets-username=<lpass_user> 
         --shared-secrets-item=<pass_folder_item> 
         [--dangerous-overwrite-vault] 
         [--shared-secrets-folder=<pass_folder>] 
         [--secrets-password=<lpass_password>]
       landscape [options]
        landscaper update-yaml 
         --chart-directory=<lpass_user> 
         --destination-name=<lpass_user> 
         --destination-namespace=<lpass_user>
         [--output=<path_to_landscaper_yaml>] 
       landscape [options]
        setup install-prerequisites

Options:
    --git-branch=<git_branch>    Operate on Terraform (clouds) and Landscaper 
                                 (charts) repositories matching specified branch
                                 [default: auto-detect-branch].
    --landscaper-dir=<path>      Path to Landscaper YAML dir [default: .].                 
    --terraform-dir=<path>       Path to Terraform templates [default: ../terraform].                 
    --all-branches               Operate on all branches
    --dry-run                    Simulate, but don't converge.
    --log-level=<log_level>      Log messages at least this level [default: INFO].
    --dangerous-overwrite-vault  Allow VAULT_ADDR != http://127.0.0.1:8200 [default: false].
    --shared-secrets-folder=<pass_folder>     [default: Shared-k8s/k8s-landscaper].
"""

import docopt
import os
import subprocess
import logging
import platform

from .cloudcollection import CloudCollection
from .clustercollection import ClusterCollection
from .cloud import Cloud
from .cluster import Cluster

from .chartscollection_landscaper import LandscaperChartsCollection
from .secrets import UniversalSecrets
from .localmachine import Localmachine
from .kubernetes import (kubernetes_get_context, kubectl_use_context)
from .vault import (read_kubeconfig, write_kubeconfig)
from .prerequisites import install_prerequisites


def main():
    args = docopt.docopt(__doc__)

    loglevel = args['--log-level']
    numeric_level = getattr(logging, loglevel.upper(), None)
    if not isinstance(numeric_level, int):
        raise ValueError('Invalid log level: %s' % loglevel)
    logging.basicConfig(level=numeric_level)

    # parse arguments
    dry_run = args['--dry-run']
    cloud_selection = args['--cloud']
    cluster_selection = args['--cluster']
    namespaces_selection = args['--namespaces']
    git_branch_selection = args['--git-branch']
    if git_branch_selection == 'auto-detect-branch':
        git_branch_selection = None
    use_all_git_branches = args['--all-branches']
    landscaper_dir = args['--landscaper-dir']
    terraform_dir = args['--terraform-dir']

    if use_all_git_branches:
        git_branch_selection = None

    also_converge_cloud = args['--converge-cloud']
    also_converge_cluster = args['--converge-cluster']
    also_converge_localmachine = args['--converge-localmachine']
    # if set, write to a VAULT_ADDR env variable besides http://127.0.0.1:8200
    remote_vault_ok = args['--dangerous-overwrite-vault']

    # apply arguments
    cluster = None
    if cloud_selection:
        selected_cloud = CloudCollection.LoadCloudByName(cloud_selection)
    logging.debug("cloud_selection: {0}".format(cloud_selection))

    selected_cluster = None
    if cluster_selection:
        selected_cluster = ClusterCollection.LoadClusterByName(cluster_selection)
    logging.debug("cluster_selection: {0}".format(cluster_selection))

    logging.debug("git_branch_selection: {0}".format(git_branch_selection))

    clouds = None
    clusters = None
    charts = None
    if not args['secrets']:
        # landscape secrets overwrite --from-lastpass ...
        clouds = CloudCollection(git_branch=git_branch_selection,
                                    path_to_terraform_repo=terraform_dir)
        clusters = ClusterCollection(cloud=cloud_selection,
                                        git_branch=git_branch_selection)
    logging.debug("clouds: {0}".format(clouds))
    logging.debug("clusters: {0}".format(clusters))

    # landscape cloud ...
    if args['cloud']:
        # landscape cloud list
        if args['list']:
            if cluster_selection:
                print(selected_cluster.cloud)
            else:
                print(clouds)
        # landscape cloud converge
        elif args['converge']:
            clouds[cloud_selection].converge()


    # landscape cluster ...
    elif args['cluster']:
        # landscape cluster list
        if args['list']:
            print(clusters)
        # landscape cluster converge
        elif args['converge']:
            if also_converge_cloud:
                selected_cluster.cloud.converge()
            clusters[cluster_selection].converge()


    # landscape charts ...
    elif args['charts']:
        # TODO: figure out cluster_provisioner inside LandscaperChartsCollection
        # to pass one less parameter to LandscaperChartsCollection
        charts = LandscaperChartsCollection(path_to_landscaper_repo=landscaper_dir,
                                            context_name=cluster_selection,
                                            namespace_selection=namespaces_selection)
        logging.debug("charts: {0}".format(charts))
        # landscape charts list ...
        if args['list']:
            print(charts)
        # landscape charts converge ...
        elif args['converge']:
            if also_converge_cloud:
                selected_cluster.cloud.converge(dry_run)
            if also_converge_cluster:
                clusters[cluster_selection].converge(dry_run)
            charts.converge(dry_run)
            # set up local machine for cluster
            if also_converge_localmachine:
                localmachine = Localmachine(cluster=clusters[cluster_selection])
                localmachine.converge()

    # landscape secrets overwrite overwrite-vault-with-lastpass ...
    elif args['secrets'] and args['overwrite-vault-with-lastpass']:
        central_secrets_folder = args['--shared-secrets-folder']
        central_secrets_item = args['--shared-secrets-item']
        central_secrets_username = args['--secrets-username']
        central_secrets_password = args['--secrets-password']
        shared_secrets = UniversalSecrets(dry_run=dry_run,
                                          provider='lastpass',
                                          username=central_secrets_username,
                                          password=central_secrets_password)
        shared_secrets.overwrite_vault(shared_secrets_folder=central_secrets_folder,
                                       shared_secrets_item=central_secrets_item,
                                       use_remote_vault=remote_vault_ok)


    # landscape setup install-prerequisites ...
    elif args['setup']:
        if args['install-prerequisites']:
            install_prerequisites(platform.system())


if __name__ == "__main__":
    main()
