# Landscape: Place kubernetes clusters, charts, and secrets into clouds.
  
  This tool unites components of the Kubernetes ecosystem:
   - Cloud management (hosting the Kubernetes clusters)
   - Kubernetes Cluster management
   - Helm Chart deployment and deletion (via Landscaper)
   - Kubernetes secrets (flow: [LastPass ->] Vault -> Landscaper -> K8S Secrets)

   Optionally a command exists, pulls centralized shared secrets from LastPass into Vault.

## Supported systems
 - Cloud: terraform, minikube
 - Cluster: GKE, minikube, unmanaged (unmanaged bypasses cloud setup)

## Features
Deploy k8s clusters + apps (Helm Charts) to:
- minikube
- GKE
- Any other Kubernetes cluster to which you have credentials

It does this in a portable way, by abstracting cluster provisioning, and centralizing secrets in Vault

Apps are deployed via Helm Charts, with secrets kept in Vault until deployment


## Wrapping landscaper tool
To apply a single namespace in landscaper, the command is:
```
landscaper apply -v --namespace=jenkins --context=minikube ./all/jenkins/jenkins.yaml
```

This requires environment variables set.

To read secrets from Vault and sets the secrets in environment variable(s)) use the landscape-cli wrapper tool:

```
# Run below while cd'd to landscaper directory root
export VAULT_ADDR=<vault server address>
landscape charts converge --cluster=minikube --namespaces=jenkins
```

## Example Usage
 - List all clouds stored in Vault
```
landscape cloud list
```

 - List all clusters
```
landscape cluster list
```

 - Converge cloud
```
landscape cloud converge
```

 - Converge cloud then cluster
```
landscape cluster converge --converge-cloud
```

 - Verify cloud, clusters, and charts can be pulled from Vault
```
for cloud_name in `landscape cloud list`; do
        echo saw cloud ${cloud_name}
        for cluster_name in `landscape cluster list --cloud=${cloud_name}`; do
	        echo saw cluster ${cluster_name}
            landscape charts list --cluster=${cluster_name}
        done
done

for cluster_name in `landscape cluster list`; do
	echo saw cluster ${cluster_name}
	for cloud_name in `landscape cloud list --cluster=${cluster_name}`; do
		echo saw cloud ${cloud_name}
	done
done
```

## minikube HTTP Proxy
Applies to minikube clusters

If set, HTTP_PROXY and HTTPS_PROXY will be used for docker image caching
Run squid on your local machine for fastest results
```brew install squid && brew services start squid```

Set up your local ~/.bash_profile:
```
cat << EOF > ~/.bash_profile
DEFAULT_INTERFACE=`netstat -rn | grep default | head -n 1 | awk '{ print $NF }'`
DEFAULT_IP=`ifconfig $DEFAULT_INTERFACE | grep inet | awk '{ print $2 }'`
export https_proxy=http://${DEFAULT_IP}:3128
export HTTPS_PROXY="$https_proxy"
export http_proxy="$https_proxy"
export HTTP_PROXY="$https_proxy"
export no_proxy=http.chartmuseum.svc.cluster.local,storage.googleapis.com
EOF
```

open a new shell to use these environment variables

# Create a virtualenv and activate it
```
python3.6 -m venv ~/venv
source ~/venv/bin/activate

# Install landscape tool
pip install --upgrade .

# install prerequisites
landscape setup install-prerequisites

## Bootstrap local setup
Deploys to local docker containers:
 - hashicorp vault
 - chartmuseum Helm chart server

## Git Branch Subscriptions
- clouds are tied to git branches for a terraform repo [terraform repo](terraform-templates)
- clusters are tied to git branches for a landscaper chart repo [landscaper repo](charts)

The landscape tool in this repo is careful not to apply git branches
to the wrong clusters and clouds, unless forced on the command line with --force

## Getting Started (cloud-mode via Terraform)
 - Add Jenkinsfile to a Jenkins job
 - Open https://http.jenkins.svc.cluster.local in your browser

## Command-line cluster-specific provisioning

### minikube

 - Import minikube ca.crt into your MacOS keychain
```
sudo security add-trusted-cert -d -r trustRoot -k /Library/Keychains/System.keychain ~/.minikube/ca.crt
```

 - deploy cluster (minikube + helm charts)

 Pulls secrets from LastPass and puts them in a local dev-vault container
 Serves Helm Chart repo in a local dev-chartmuseum container, backed by GCS
```
make CLUSTER_NAME=minikube
     SHARED_SECRETS_USERNAME=lastpass@email.address
     DEPLOY_LOCAL_REPOS=true
     GOOGLE_STORAGE_BUCKET=helm-charts-staging-123456
     DANGER_DEPLOY_LASTPASS_SECRETS=true
```

 - terraform
```

### GKE
1. list clusters
```
landscape cluster list
```

2. deploy cluster (GCE/GKE terraform template + helm charts)
```
make CLUSTER_NAME=gke_staging-123456_us-west1-a_master
```

or
```
landscape charts converge --git-branch=${BRANCH_NAME} --cluster=${CLUSTER_NAME} --converge-cluster --converge-cloud
```

## Once cluster is up
- Verify that the cluster is running by issuing the command:
```
kubectl version --context=${CONTEXT_NAME}
```

- generate OpenVPN profile to connect to the cluster
```
helm status openvpn-openvpn | grep -v '^.*#' | sed -e '1,/generate_openvpn_profile:/d'
```

- Copy and paste the output into a shell to generate a Viscosity profile setup

- open the VPN profile  (it has a .ovpn extension)

- Username and password are what is in Vault /openvpn/ sub-key


# Connect to a VPN inside your cluster
helm status openvpn-openvpn # copy the create_viscosity_profile section
                            # and run it in your shell
open minikube-master.ovpn # Import Viscosity profile into MacOS

# Connect to minikube-master. admin credentials are pulled from LastPass
# via the above `make` command.

# Open https://http.jenkins.svc.cluster.local in your browser
```

## Prerequisites
Should be installed automatically, if missing
 - kubectl
 - vault
 - helm
 - vault
 - minikube
 - landscaper
 - [Google Cloud SDK](https://cloud.google.com/sdk/)

For gcr.io docker auth config on MacOSX, your ~/.docker/config.json file must
have the `"credsStore": "osxkeychain"` line removed. Then run `docker login` to
the registry you want to use for docker images. The file will be copied in as
part of the minikube start-up.

## Credentials

LastPass credentials are used to retrieve a shared set of secrets
These secrets are then passed into Vault - used for Terraform and Helm secrets

## Vault paths
```
# GCE credentials JSON
/secret/terraform/$(GCE_PROJECT_ID)/auth['credentials']
# Kubeconfig secrets (used by Jenkins)
/secret/k8s_contexts/$(CONTEXT_NAME)
# Helm secrets, deployed via Landscaper
/secret/landscape/$(GIT_BRANCH)
```

## Troubleshooting

- Error messages
GCloud credentials failing
```
Failed to load backend:
Error configuring the backend "gcs": Failed to configure remote backend "gcs": google: could not find default credentials.
```

This means you don't have GOOGLE_CREDENTIALS set. Run `gcloud auth activate-service-account` to remedy.

- minikube clock out of sync
Fix:
```
minikube ssh -- docker run -i --rm --privileged --pid=host debian nsenter -t 1 -m -u -n -i date -u $(date -u +%m%d%H%M%Y)
```

- chartmuseum helm chart server
Requires command `gcloud auth application-default login` having been run. Mounts your own google credentials json inside of the chartmuseum container.
