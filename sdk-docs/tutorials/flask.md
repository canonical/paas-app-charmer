# Write your first Kubernetes charm using the PaaS app charmer

In this tutorial you will learn how to prepare a rock and write a Kubernetes charm for a Flask application in accelerated fashion using the charm SDK with the PaaS app charmer, so you can have it up and running with Juju in no time!

[note type=information status]
:open_book:  **rock** <br>An Ubuntu LTS-based OCI compatible container image designed to meet security, stability, and reliability requirements for cloud-native software.

:open_book: **charm** <br>
A package consisting of YAML files + Python code that will automate every aspect of an application's life so it can be easily orchestrated with Juju.

:open_book: **PaaS app charmer** <br>
The standard charm SDK tooling (Charmcraft, Ops, etc.) plus a Rockcraft extension (`flask-framework`), a Charmcraft extension (`flask-framework`), and related Python libraries, the collective purpose of which is to give you a richer starting template so you can have your Flask application rocked, charmed, and then deployed, integrated, and managed with Juju in no time.
[/note]

## What you’ll need:

* A work station, e.g., a laptop, with amd64 architecture and which has
  sufficient resources to launch a virtual machine with 4 CPUs, 8 GB RAM, and 30
  GB disk space
* Familiarity with Linux
* Familiarity with Juju (make sure to complete at least the [Get started with Juju](https://juju.is/docs/juju/tutorial) tutorial)

## What you’ll do:

- [Set things up](#set-things-up)
- [Use the charm SDK + PaaS app charmer to quickly rock and charm a Flask application](#use-the-charm-sdk-+-paas-app-charmer-to-quickly-rock-and-charm-a-flask-application)
    - [Enable `juju deploy sample-flask`](#enable-juju-deploy-sample-flask)
    - [Enable `juju config sample-flask language=<language>`](#enable-juju-config-sample-flask-languagelanguage)
    - [Enable `juju integrate sample-flask mysql-k8s`](#enable-juju-integrate-sample-flask-mysql-k8s)
- [Tear things down](#tear-things-down)

[note type=positive status="At any point, to give feedback or ask for help"]
Don't hesitate to get in touch on [Matrix](https://matrix.to/#/#charmhub-charmdev:ubuntu.com) or [Discourse](https://discourse.charmhub.io/) (or follow the "Help improve this document in the forum" on the bottom of this doc to comment directly on the doc).
[/note]


## Set things up

You will need a Flask application that meets the requirements for the PaaS app charmer (i.e., its project directory contains a `requirements.txt` file declaring all Python dependencies and its WSGI path is `app:app`). You will also need the charm SDK + PaaS app charmer supplement, Juju, and a Kubernetes cloud. And it's a good idea if you can do all your work in an isolated development environment. You can get all of this by following our generic development setup guide, with some annotations.

> See
  [Set up your development environment automatically](https://juju.is/docs/sdk/dev-setup#heading--set-up-your-development-environment-automatically), with the following changes:
> - At the directory step, instead of creating a new directory, clone `git clone https://github.com/canonical/sample-flask.git`. This will create a `sample-flask` directory with the files for an example Flask application.
> - At the VM setup step, inside the VM, refresh Rockcraft and Charmcraft to `latest/edge`:  `sudo snap refresh rockcraft --channel latest/edge` , `sudo snap refresh charmcraft --channel latest/edge`. This will ensure that your VM is PaaS-app-charmer-ready.
> - At the cloud selection step, choose `microk8s`.
> - At the mount step: Make sure to read the box with tips on how to edit files locally while running them inside the VM! <br><br>
> All set!

## Use the charm SDK + PaaS app charmer to quickly rock and charm a Flask application

Time to put the charm SDK + PaaS app charmer to work!

### Enable `juju deploy sample-flask`

Let’s rock and charm our `sample-flask` application so that a user can successfully install it on any Kubernetes cloud simply by running `juju deploy sample-flask`!

In your Multipass VM shell, enter your Flask project directory, run `rockcraft init --profile flask-framework` to initialise the rockcraft project file for your Flask application, and inspect the result:

```bash
# Enter your charm directory:
ubuntu@charm-dev-vm:~$ cd sample-flask/

# Initialise the rockcraft project file:
ubuntu@charm-dev-vm:~/sample-flask$ rockcraft init --profile flask-framework

# Inspect the result:
ubuntu@charm-dev-vm:~/sample-flask$ ls rockcraft.yaml
rockcraft.yaml
```

In your local editor, open the `rockcraft.yaml` file and customise the summary and description.

Next, in your Multipass VM shell, inside your project directory, run
`rockcraft pack` to pack the rock. It may take a few minutes the first time
around but, when it’s done, your Flask project should contain a `.rock` file:

```bash
# Pack the Flask application into a '.rock' file:
ubuntu@charm-dev-vm:~/sample-flask$ rockcraft pack
deleting current features configuration
deleting current features configuration
Packed sample-flask_0.1_amd64.rock

# Inspect the results -- your Flask project directory should contain a .rock file:
ubuntu@charm-dev-vm:~/sample-flask$ ls
LICENSE  app.py  requirements.txt  rockcraft.yaml  sample-flask_0.1_amd64.rock  templates
```

Next, on your Multipass VM, upload the rock to your MicroK8s cloud's built-in container registry. Sample session:

```bash
# Use the skopeo, an container images utility tool, bundled with rockcraft to upload the rock image to microk8s built-in registry (localhost:32000)
ubuntu@charm-dev-vm:~/sample-flask$ /snap/rockcraft/current/bin/skopeo --insecure-policy copy --dest-tls-verify=false oci-archive:sample-flask_0.1_amd64.rock docker://localhost:32000/sample-flask:main
Getting image source signatures
Copying blob 29202e855b20 done
Copying blob 1ae6062392ff done
Copying blob 2125f5130a12 done
Copying blob 2f1020cd27a0 done
Copying blob 6ad38169ff53 done
Copying config cd33d09f74 done
Writing manifest to image destination
Storing signatures
```

Next, on your Multipass VM, in your Flask project directory, create a subdirectory for the charm, enter it, and use Charmcraft to initialise a charm with the PaaS app charmer's  `flask-framework` profile:

```bash
# Create the charm directory:
ubuntu@charm-dev-vm:~/sample-flask$ mkdir charm

# Enter the charm directory:
ubuntu@charm-dev-vm:~/sample-flask$ cd charm

# Initialise the charm tree structure with the 'flask-framework' profile:
ubuntu@charm-dev-vm:~/sample-flask/charm$ charmcraft init --profile flask-framework
Charmed operator package file and directory tree initialised.

Now edit the following package files to provide fundamental charm metadata
and other information:

charmcraft.yaml
src/charm.py
README.md
```

In your local editor, open the `charm/charmcraft.yaml` file, change the name to  `sample-flask` and customise the summary and the description. (You can leave any commented parts untouched for now -- we will revisit some of them later.)

Next, on your Multipass VM, in the charm directory, use Charmcraft to download all the charm libraries necessary for a PaaS app charmer Flask charm:

[note type=information]
:open_book: **charm library**<br>
A Python file published by a charm developer to easily share and reuse auxiliary
logic related to charms.
[/note]

[note type=positive]
**Finding this step tedious?** We are working to simplify it. Updates coming up soon!
[/note]

```bash
ubuntu@charm-dev-vm:~/sample-flask/charm$ charmcraft fetch-lib charms.traefik_k8s.v2.ingress
Library charms.traefik_k8s.v2.ingress version 2.8 downloaded.

ubuntu@charm-dev-vm:~/sample-flask/charm$ charmcraft fetch-lib charms.observability_libs.v0.juju_topology
Library charms.observability_libs.v0.juju_topology version 0.6 downloaded.

ubuntu@charm-dev-vm:~/sample-flask/charm$ charmcraft fetch-lib charms.grafana_k8s.v0.grafana_dashboard
Library charms.grafana_k8s.v0.grafana_dashboard version 0.35 downloaded.

ubuntu@charm-dev-vm:~/sample-flask/charm$ charmcraft fetch-lib charms.loki_k8s.v0.loki_push_api
Library charms.loki_k8s.v0.loki_push_api version 0.25 downloaded.

ubuntu@charm-dev-vm:~/sample-flask/charm$ charmcraft fetch-lib charms.data_platform_libs.v0.data_interfaces
Library charms.data_platform_libs.v0.data_interfaces version 0.26 downloaded.

ubuntu@charm-dev-vm:~/sample-flask/charm$ charmcraft fetch-lib charms.prometheus_k8s.v0.prometheus_scrape
Library charms.prometheus_k8s.v0.prometheus_scrape version 0.44 downloaded.

ubuntu@charm-dev-vm:~/sample-flask/charm$ charmcraft fetch-lib charms.redis_k8s.v0.redis
Library charms.redis_k8s.v0.redis version 0.5 downloaded.
```

Next, use Charmcraft to pack the charm. It may take a few minutes the first time around but, when it’s done, your charm project should contain a .charm file:

```bash
# Set the environment variable to enable experimental extensions and pack the charm into a '.charm' file:
ubuntu@charm-dev-vm:~/sample-flask/charm$ charmcraft pack
Packed sample-flask_ubuntu-22.04-amd64.charm

# Inspect the results -- your charm directory should contain a .charm file:
ubuntu@charm-dev-vm:~/sample-flask/charm$ ls
charmcraft.yaml  lib  requirements.txt  sample-flask_ubuntu-22.04-amd64.charm  src
```

Now, open a new shell into your Multipass VM and use it to configure the Juju
log verbosity levels and to start a live debug session:

```bash
# Set your logging verbosity level to `DEBUG`:
ubuntu@charm-dev-vm:~$  juju model-config logging-config="<root>=WARNING;unit=DEBUG"

# Start a live debug session:
ubuntu@charm-dev-vm:~$  juju debug-log
```

In your old VM shell, in your `sample-flask` directory, use Juju to deploy your charm, passing as a resource the rock you've uploaded to the container registry. If all has gone well, you
should soon be able to see your deployed application and connect to it:

```bash
# Deploy the PaaS app charmer Flask charm for the sample-flask Flask application
# We need to supply the resources to Juju, including the sample-flask rock we just created and pushed to the microk8s registry
# and the image prom/statsd-exporter:v0.24.0 used for adding observability to the Flask application
ubuntu@charm-dev-vm:~/sample-flask$ juju deploy ./charm/sample-flask_ubuntu-22.04-amd64.charm sample-flask --resource flask-app-image=localhost:32000/sample-flask:main
Located local charm "sample-flask", revision 0
Deploying "sample-flask" from local charm "sample-flask", revision 0 on ubuntu@22.04/stable

# Check the deployment status
# (use --watch 1s to update it automatically at 1s intervals):
ubuntu@charm-dev-vm:~/sample-flask$ juju status
Model        Controller  Cloud/Region        Version  SLA          Timestamp
welcome-k8s  microk8s    microk8s/localhost  3.1.7    unsupported  10:14:28Z

App           Version  Status  Scale  Charm         Channel  Rev  Address         Exposed  Message
sample-flask           active      1  sample-flask             0  10.152.183.175  no

Unit             Workload  Agent  Address      Ports  Message
sample-flask/0*  active    idle   10.1.30.206


# Test that the service works by using curl to send a request to the
# Flask service (IP from the 'juju status' output):
ubuntu@charm-dev-vm:~/sample-flask$ curl 10.1.30.206:8000
<h1>Hello</h1>
```



### Enable `juju config sample-flask language=<language>`

When you connected to your deployed Flask application, it returned a greeting in English. On your Multipass VM, in your `sample-flask` root directory, update the application so it will offer this greeting in other languages too:

```bash
# Check out the 'feat-translation' branch to add multi-language functionality:
ubuntu@charm-dev-vm:~/sample-flask$ git checkout feat-translation
Branch 'feat-translation' set up to track remote branch 'feat-translation' from 'origin'.
Switched to a new branch 'feat-translation'
```

Now, update the rock:

```bash
# Change the version of the rock in the rockcraft.yaml file.
# (This is not required but it's good practice.)
ubuntu@charm-dev-vm:~/sample-flask$ sed -i "s/version: '0.1'/version: '0.2'/g" rockcraft.yaml

# Run the pack command again:
ubuntu@charm-dev-vm:~/sample-flask$ rockcraft pack
deleting current features configuration
deleting current features configuration
Packed sample-flask_0.2_amd64.rock

# Verify that we have the version 0.2 rock packed
ubuntu@charm-dev-vm:~/sample-flask$ ls
LICENSE  app.py  charm  charmcraft_2.5.0.post12+gitcc670c9_amd64.snap  requirements.txt  rockcraft.yaml  sample-flask_0.1_amd64.rock  sample-flask_0.2_amd64.rock  templates

# Push the rock image to the microk8s container registry, we are using a different tag 'sample-flask:translation' this time
ubuntu@charm-dev-vm:~/sample-flask$ /snap/rockcraft/current/bin/skopeo --insecure-policy copy --dest-tls-verify=false oci-archive:sample-flask_0.2_amd64.rock docker://localhost:32000/sample-flask:translation
Getting image source signatures
Copying blob 29202e855b20 skipped: already exists
Copying blob 99042ffb5abc done
Copying blob 137bcaaf927d done
Copying blob c9b675b45b83 done
Copying blob 47e8f82d22e0 done
Copying config 8cfd0af307 done
Writing manifest to image destination
Storing signatures
```

Next, let’s evolve our charm so that a user can successfully choose which language they want to be greeted in simply by running `juju config sample-flask language=<language>` !

1. In your local editor, in your `charm/charmcraft.yaml` file, define the configuration option as below:

```yaml
config:
  options:
    language:
      description: |
        Language for the greeting message in ISO 639-2 code.
        Valid options are: "ara", "eng", "fra", "hin", "por", "spa", "swa", and "zho".
      default: "eng"
      type: string
```

2. Then, in your Multipass VM shell, inside the charm directory, repack the charm, then
refresh it in the Juju model, and verify that the newly defined configuration option exists and works:

```bash
# Repack the charm, the old .charm file will be overwritten
ubuntu@charm-dev-vm:~/sample-flask/charm$ charmcraft pack
Packed sample-flask_ubuntu-22.04-amd64.charm

# Refresh the sample-flask juju application with the repacked charm
# Remember to provide the new rock image (localhost:32000/sample-flask:translation) in the resource we just built during the refresh
ubuntu@charm-dev-vm:~/sample-flask/charm$ juju refresh sample-flask --path=./sample-flask_ubuntu-22.04-amd64.charm --resource flask-app-image=localhost:32000/sample-flask:translation
Added local charm "sample-flask", revision 1, to the model
no change to endpoints in space "alpha": grafana-dashboard, ingress, logging, metrics-endpoint, secret-storage

# Verify that the new 'language' configuration option is available:
ubuntu@charm-dev-vm:~/sample-flask/charm$ juju config sample-flask | grep -A 7 language
  language:
    default: eng
    description: |
      Language for the greeting message in ISO 639‑2 code.
      Valid options are: "ara", "eng", "fra", "hin", "por", "spa", "swa", and "zho".
    source: default
    type: string
    value: eng

# Change the 'language' config to 'spa':
ubuntu@charm-dev-vm:~/sample-flask/charm$ juju config sample-flask language=spa

# Get the latest unit IP address after refresh using the juju status command
ubuntu@charm-dev-vm:~/sample-flask/charm$ juju status
Model        Controller  Cloud/Region        Version  SLA          Timestamp
welcome-k8s  microk8s    microk8s/localhost  3.1.7    unsupported  06:25:08Z

App           Version  Status  Scale  Charm         Channel  Rev  Address         Exposed  Message
sample-flask           active      1  sample-flask             1  10.152.183.175  no

Unit             Workload  Agent  Address      Ports  Message
sample-flask/0*  active    idle   10.1.30.207

# Inspect the new greeting message
ubuntu@charm-dev-vm:~/sample-flask/charm$ curl 10.1.30.207:8000
<h1 dir="auto">Hola</h1>
```

All set!

### Enable `juju integrate sample-flask mysql-k8s`

Our application is ready to greet people, but it would be nice to know how many visitors there are! On your Multipass VM, in your `sample-flask` directory, update the application so it can count visitors in a PostgreSQL database:

```bash
ubuntu@charm-dev-vm:~/sample-flask$ git checkout feat-database
Branch 'feat-database' set up to track remote branch 'feat-database' from 'origin'.
Switched to a new branch 'feat-database'
```

Now, update the rock:

```bash
# Change the version of rock in the rockcraft.yaml file again:
ubuntu@charm-dev-vm:~/sample-flask$ sed -i "s/version: '0.2'/version: '0.3'/g" rockcraft.yaml

# Repack the rock:
ubuntu@charm-dev-vm:~/sample-flask$ rockcraft pack
deleting current features configuration
deleting current features configuration
Packed sample-flask_0.3_amd64.rock

# Push the rock to the MicroK8s container image registry 
# (use the tag 'sample-flask:database' this time):
ubuntu@charm-dev-vm:~/sample-flask$ /snap/rockcraft/current/bin/skopeo --insecure-policy copy --dest-tls-verify=false oci-archive:sample-flask_0.3_amd64.rock docker://localhost:32000/sample-flask:database
Getting image source signatures
Copying blob 29202e855b20 skipped: already exists
Copying blob b6eb7364648a done
Copying blob f0c09d32dd6a done
Copying blob bb9e380ad050 done
Copying blob a151c1ce9737 done
Copying config 4a65989048 done
Writing manifest to image destination
Storing signatures
```

Finally, let's evolve our charm so that a charm user can integrate the application deployed from it with PostgreSQL simply by running `juju integrate sample-flask postgresql-k8s` (taking advantage of the existing Kubernetes charm for PostgreSQL)!

1. In your `charm/charmcraft.yaml` file, declare a name with role `requires`, name `postgresql`, and interface `postgresql_client` to say that this charm can consume a Postgresql database charm.

```yaml
requires:
  postgresql:
    interface: postgresql_client
    limit: 1
```

2. In your Multipass VM, repack and refresh the charm, then deploy `postgresql-k8s` and verify that your charm can integrate with it:

[note type=information]
**If, at the integrate step, you see the following error:**
```bash
ubuntu@charm-dev-vm:~/sample-flask/charm$ juju integrate sample-flask postgresql-k8s
ERROR no relations found
```
In your charm directory, run `charmcraft clean`, then pack and refresh the charm again.

(The issue is being investigated but, for now, this seems to solve the problem.)

[/note]

```bash
ubuntu@charm-dev-vm:~/sample-flask$ cd charm/
ubuntu@charm-dev-vm:~/sample-flask/charm$ charmcraft pack
Packed sample-flask_ubuntu-22.04-amd64.charm

ubuntu@charm-dev-vm:~/sample-flask/charm$ juju refresh sample-flask --path=./sample-flask_ubuntu-22.04-amd64.charm --resource flask-app-image=localhost:32000/sample-flask:database
Added local charm "sample-flask", revision 2, to the model
adding endpoint "postgresql" to default space "alpha"
no change to endpoints in space "alpha": grafana-dashboard, ingress, logging, metrics-endpoint, secret-storage

# Check status -- it should appear as blocked 
# because your charm now expects a database, and you haven't given it one yet:
ubuntu@charm-dev-vm:~/sample-flask/charm$ juju status
Model        Controller  Cloud/Region        Version  SLA          Timestamp
welcome-k8s  microk8s    microk8s/localhost  3.1.7    unsupported  08:12:42Z

App             Version  Status   Scale  Charm           Channel    Rev  Address         Exposed  Message
sample-flask             waiting      1  sample-flask                 2  10.152.183.175  no       waiting for units to settle down

Unit               Workload  Agent  Address      Ports  Message
sample-flask/0*    blocked   idle   10.1.30.210         Webserver configuration check failed, please review your charm configuration or database relation

# Deploy the postgresql-k8s charm from the 14/stable channel
# ('--trust' is needed because the postgresql-k8s charm 
# needs access to the cloud to update some Kubernetes resources): 
ubuntu@charm-dev-vm:~/sample-flask$ juju deploy postgresql-k8s --channel 14/stable --trust
Located charm "postgresql-k8s" in charm-hub, revision 177
Deploying "postgresql-k8s" from charm-hub charm "postgresql-k8s", revision 177 in channel 14/stable on ubuntu@22.04/stable

# Wait for the postgresql-k8s charm to become active
# (it might take a few minutes):
ubuntu@charm-dev-vm:~/sample-flask$ juju status
Model        Controller  Cloud/Region        Version  SLA          Timestamp
welcome-k8s  microk8s    microk8s/localhost  3.1.7    unsupported  08:06:40Z

App             Version  Status  Scale  Charm           Channel    Rev  Address         Exposed  Message
postgresql-k8s  14.9     active      1  postgresql-k8s  14/stable  177  10.152.183.228  no
sample-flask             active      1  sample-flask                 2  10.152.183.175  no

Unit               Workload  Agent  Address      Ports  Message
postgresql-k8s/0*  active    idle   10.1.30.209
sample-flask/0*    blocked   idle   10.1.30.210         Webserver configuration check failed, please review your charm configuration or database relation

# Integrate the sample-flask charm and the postgresql-k8s charm:
ubuntu@charm-dev-vm:~/sample-flask/charm$ juju integrate sample-flask postgresql-k8s

# Wait for the sample-flask charm and the postgresql-k8s charm 
# to become active:
ubuntu@charm-dev-vm:~/sample-flask/charm$ juju status
Model        Controller  Cloud/Region        Version  SLA          Timestamp
welcome-k8s  microk8s    microk8s/localhost  3.1.7    unsupported  10:00:13Z

App             Version  Status  Scale  Charm           Channel    Rev  Address         Exposed  Message
postgresql-k8s  14.9     active      1  postgresql-k8s  14/stable  177  10.152.183.228  no       Primary
sample-flask             active      1  sample-flask                 5  10.152.183.175  no

Unit               Workload  Agent  Address      Ports  Message
postgresql-k8s/0*  active    idle   10.1.30.209         Primary
sample-flask/0*    active    idle   10.1.30.210

# Use the IP address from juju status to access the sample-flask website 
# (note how the visitor counter goes up each time):
ubuntu@charm-dev-vm:~/sample-flask/charm$ curl 10.1.30.210:8000
<h1 dir="auto">Hola</h1>
<small>Visitors: 1</small>
ubuntu@charm-dev-vm:~/sample-flask/charm$ curl 10.1.30.211:8000
<h1 dir="auto">Hola</h1>
<small>Visitors: 2</small>
```
