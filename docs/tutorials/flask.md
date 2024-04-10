# Write your first Kubernetes charm using the PaaS app charmer

In this tutorial you will learn how to use the PaaS app charmer to convert your
existing Flask application to a Kubernetes charm for Juju.

What you’ll need:

* A work station, e.g., a laptop, with amd64 architecture and which has
  sufficient resources to launch a virtual machine with 4 CPUs, 8 GB RAM, and 30
  GB disk space
* Familiarity with Linux
* Familiarity with Juju

What you’ll do:

* [Study your application](#study-your-application)
* [Set up your development environment automatically](#set-up-your-development-environment-automatically)

1. Enable `juju deploy sample-flask`
2. Enable `juju config sample-flask language=<language>`
3. Enable `juju integrate sample-flask mysql-k8s`

* Clean up: Destroy your test environment

## Study your application

In this tutorial we will be converting a small educational Flask application -
`sample-flask` into a charm.

You can check out the source code of the Flask application from the GitHub
repository (`git clone https://github.com/canonical/sample-flask.git`).

### Check that your flask application meets the PaaS app charmer prerequisites

The sample Flask application already satisfies the requirements of the PaaS app
charmer. For future Flask applications, make sure your Flask application
satisfies the following properties:

* `requirements.txt` exists in your project root declaring all Python
  dependencies
* The WSGI path for your Flask framework application is `app:app`

## Set up your development environment automatically

> See
  [Set up your development environment automatically](https://juju.is/docs/sdk/dev-setup#heading--set-up-your-development-environment-automatically)
  for instructions on how to set up your development environment so that it’s
  ready for you to test-deploy your charm. At the charm directory step, instead
  of creating a new directory, clone the example project
  (`git clone https://github.com/canonical/sample-flask.git`). At the cloud
  step, choose microk8s. You will also need to install `rockcraft` using
  `sudo snapp install rockcraft --channel latest/edge` and switch to the
  `latest/edge` channel for `charmcraft` using
  `sudo snap refresh charmcraft --channel latest/edge`.

* Going forward:

  * Use your host machine (on Linux, cd ~/sample-flask) to create and edit files
    in the Flask project directory. This will allow you to use your favorite
    local editor.
  * Use the Multipass VM shell (on Linux,
    `ubuntu@charm-dev-vm:~$ cd ~/sample-flask`) to run Charmcraft, Rockcraft,
    and Juju commands.

* At any point:

  * To exit the shell, press mod key + C or type exit.
  * To stop the VM after exiting the VM shell, run
    `multipass stop charm-dev-vm`.
  * To restart the VM and re-open a shell into it, type
    `multipass shell charm-dev-vm`.

## Enable `juju deploy sample-flask`

The first step of charmify the Flask application is to create a rock.
Rocks are Ubuntu LTS-based OCI compatible container images that are designed to
meet cloud-native software’s security, stability, and reliability requirements.
The charm we are building will use the rock to start the Flask application in
the Kubernetes environment.

In your Multipass VM shell, enter your Flask project directory, run
`rockcraft init --profile flask-framework` to initialise the rockcraft project
file for your Flask application, and inspect the result. Sample session:

```bash
# Enter your charm directory:
ubuntu@charm-dev-vm:~$ cd sample-flask/

# Initialise the rockcraft project file:
ubuntu@charm-dev-vm:~/sample-flask$ rockcraft init --profile flask-framework

# Inspect the result:
ubuntu@charm-dev-vm:~/sample-flask$ ls rockcraft.yaml
rockcraft.yaml
```

In your local editor, open the `rockcraft.yaml` file and customise its contents
as below (you only have to edit the title, summary, and description):

```yaml
# (Required)
name: sample-flask

# (Required)
base: ubuntu@22.04 # the base environment for this Flask application

version: '0.1' # just for humans. Semantic versioning is recommended

# (Required)
summary: A rock for the sample-flask Flask application

description: |
    A rock for the sample-flask Flask application, built with the PaaS app charmer rockcraft extension.

    This rock will be used by a sample-flask charm also built with the PaaS app charmer to
    deploy and manage the sample-flask Flask application in a Kubernetes environment.

license: GPL-3.0 # your application's SPDX license

# (Required)
platforms: # The platforms this ROCK should be built on and run on
    amd64:

# To ensure the flask-framework extension works properly, your Flask application
# should have an `app.py` file with an `app` object as the WSGI entrypoint.
extensions:
    - flask-framework

# Uncomment the sections you need and adjust according to your requirements.
# parts:
#   flask-framework/dependencies:
#     stage-packages:
#       # list required packages or slices for your flask application below.
#       - libpq-dev
#
#   flask-framework/install-app:
#     prime:
#       # By default, only the files in app/, templates/, static/, and app.py
#       # are copied into the image. You can modify the list below to override
#       # the default list and include or exclude specific files/directories
#       # in your project.
#       # Note: Prefix each entry with "flask/app/" followed by the local path.
#       - flask/app/.env
#       - flask/app/app.py
#       - flask/app/webapp
#       - flask/app/templates
#       - flask/app/static
```

Next, in your Multipass VM shell, inside your project directory, run
`rockcraft pack` to pack the rock. It may take a few minutes the first time
around but, when it’s done, your Flask project should contain a `.rock` file.
Sample session:

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

After the rock is built, we need to push the rock image to a container registry
so the rock image can be used in the Kubernetes environment. In your Multipass
VM, the microk8s built-in container registry should already been enabled, and we
will use that for this tutorial.

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

Now it's the time to build the charm. We need to create a charm directory
(`mkdir -p charm/`) inside the Flask project directory to hold the charm related
files.

```bash
# make the charm directory and change directory into the new charm directory
ubuntu@charm-dev-vm:~/sample-flask$ mkdir charm
ubuntu@charm-dev-vm:~/sample-flask$ cd charm
ubuntu@charm-dev-vm:~/sample-flask/charm$
```

In the same Multipass VM shell, inside the charm directory, run
`charmcraft init --profile flask-framework` to initialise the file tree
structure for the PaaS app charmer Flask charm, and inspect the result.

```bash
# Initialise the charm tree structure:
ubuntu@charm-dev-vm:~/sample-flask/charm$ charmcraft init --profile flask-framework
Charmed operator package file and directory tree initialised.

Now edit the following package files to provide fundamental charm metadata
and other information:

charmcraft.yaml
src/charm.py
README.md
```

In your local editor, open the `charmcraft.yaml` file and customise its contents
as below (you only have to edit the title, summary, and description). You can
leave the commented part for now, we will revisit some of them later:

```yaml
# This file configures Charmcraft.
# See https://juju.is/docs/sdk/charmcraft-config for guidance.

# (Required)
name: sample-flask

# (Required)
type: charm

# (Required for 'charm' type)
bases:
  - build-on:
    - name: ubuntu
      channel: "22.04"
    run-on:
    - name: ubuntu
      channel: "22.04"

# (Required)
summary: The charm for the sample-flask Flask application.

# (Required)
description: |
    The charm for the sample-flask Flask application, built with the PaaS app charmer charmcraft extension.

    This charm will help you to manage your Flask application in Kubernetes environment with the Juju ecosystem.


# (Required for enabling PaaS app charmer Flask framework support)
extensions:
  - flask-framework

# Uncomment the integrations used by your application
# requires:
#   mysql:
#     interface: mysql_client
#     limit: 1
#   postgresql:
#     interface: postgresql_client
#     limit: 1
```

[Charm libraries](https://juju.is/docs/sdk/find-and-use-a-charm-library) are
Python files published by charm developers to easily share and reuse auxiliary
logic related to charms. Now we need to download all the necessary charm
libraries for the PaaS app charmer Flask charm. The PaaS app charmer Flask charm
will use a few charm libraries as well, they are not included during the
charmcraft initiation process requiring downloading separately.

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

Now we pack the charm. It may take a few minutes the first time around but, when
it’s done, your charm project should contain a .charm file. Sample session:

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

In your old VM shell, use Juju to deploy your charm. If all has gone well, you
should see your App and be able to connect to the sample Flask web server:

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
```

Finally, test that the service works by using curl to send a request to the
Flask service:
```bash
# Unit IP (10.1.30.206) can be learned from the juju status output
ubuntu@charm-dev-vm:~/sample-flask$ curl 10.1.30.206:8000
<h1>Hello</h1>
```

## Enable `juju config sample-flask language=<language>`

Let's now expand the functionality of the `sample-flask` Flask application to return the greeting in different languages.
To achieve this, we will introduce a new configuration for changing the language selection.
The PaaS app charmer Flask framework offers a variety of standard configurations; these can be explored by executing the `juju config sample-flask` command.
And it's very simple to integrating custom configurations, such as the required language option mentioned before.

Let's first checkout the `feat-translation` branch of the `sample-flask` repository to load the new version of the `sample-flask` application.

```bash
ubuntu@charm-dev-vm:~/sample-flask$ git checkout feat-translation
Branch 'feat-translation' set up to track remote branch 'feat-translation' from 'origin'.
Switched to a new branch 'feat-translation'
```

Since the `sample-flask` Flask application has changed, we need to repack the rock image and push the new image to the registry.

```bash
# Change the version of rock in the rockcraft.yaml file, this is not necessary required but a good practice
ubuntu@charm-dev-vm:~/sample-flask$ sed -i "s/version: '0.1'/version: '0.2'/g" rockcraft.yaml

# Run the pack command again
ubuntu@charm-dev-vm:~/sample-flask$ rockcraft pack
*EXPERIMENTAL* extension 'flask-framework' enabled
*EXPERIMENTAL* extension 'flask-framework' enabled
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

The next step, we need to define the new language configuration option.
In your local editor, in your `charm/charmcraft.yaml` file, define the configuration option as below:

```yaml
config:
  options:
    language:
      description: |
        Language for the greeting message in ISO 639‑2 code.
        Valid options are: "ara", "eng", "fra", "hin", "por", "spa", "swa", and "zho".
      default: "eng"
      type: string
```

Now, in your Multipass VM shell, inside the charm directory, repack the charm, refresh it in the Juju model, and inspect the results:
```bash
# Repack the charm, the old .charm file will be overwritten
ubuntu@charm-dev-vm:~/sample-flask/charm$ charmcraft pack
*EXPERIMENTAL* extension 'flask-framework' enabled
*EXPERIMENTAL* extension 'flask-framework' enabled
Created 'sample-flask_ubuntu-22.04-amd64.charm'.
Charms packed:
    sample-flask_ubuntu-22.04-amd64.charm

# Refresh the sample-flask juju application with the repacked charm
# Remember to provide the new rock image (localhost:32000/sample-flask:translation) in the resource we just built during the refresh
ubuntu@charm-dev-vm:~/sample-flask/charm$ juju refresh sample-flask --path=./sample-flask_ubuntu-22.04-amd64.charm --resource flask-app-image=localhost:32000/sample-flask:translation --resource statsd-prometheus-exporter-image=prom/statsd-exporter:v0.24.0
Added local charm "sample-flask", revision 1, to the model
no change to endpoints in space "alpha": grafana-dashboard, ingress, logging, metrics-endpoint, secret-storage

# Verify that the new 'language' configuration option is available
ubuntu@charm-dev-vm:~/sample-flask/charm$ juju config sample-flask | grep -A 7 language
  language:
    default: eng
    description: |
      Language for the greeting message in ISO 639‑2 code.
      Valid options are: "ara", "eng", "fra", "hin", "por", "spa", "swa", and "zho".
    source: default
    type: string
    value: eng
```

Now we are able to change the language setting of the `sample-flask` Flask application.

```bash
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

## Enable `juju integrate sample-flask mysql-k8s`

Let's enhance the sample-flask Flask application by adding a new feature: basic visitor analytics.
To implement this feature, it's necessary to connect the sample-flask Flask application to a database.
The Juju ecosystem offers a range of high quality database charms which can be seamlessly integrated with the PaaS app charmer charms.

First, checkout the `feat-database` branch of the `sample-flask` repository and rebuild the rock image.

```bash
ubuntu@charm-dev-vm:~/sample-flask$ git checkout feat-database
Branch 'feat-database' set up to track remote branch 'feat-database' from 'origin'.
Switched to a new branch 'feat-database'

# Change the version of rock in the rockcraft.yaml file again, repack the rock image
ubuntu@charm-dev-vm:~/sample-flask$ sed -i "s/version: '0.2'/version: '0.3'/g" rockcraft.yaml
ubuntu@charm-dev-vm:~/sample-flask$ rockcraft pack
*EXPERIMENTAL* extension 'flask-framework' enabled
*EXPERIMENTAL* extension 'flask-framework' enabled
Packed sample-flask_0.3_amd64.rock

# Push the rock image to the microk8s container registry, use the tag 'sample-flask:database' this time
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

Then, in your `charm/charmcraft.yaml` file, add the declaration for requiring the connectivity to a postgresql database charm.

```yaml
requires:
  postgresql:
    interface: postgresql_client
    limit: 1
```

After the update, we can repack and refresh the charm in the VM:

```bash
ubuntu@charm-dev-vm:~/sample-flask$ cd charm/
ubuntu@charm-dev-vm:~/sample-flask/charm$ charmcraft pack
*EXPERIMENTAL* extension 'flask-framework' enabled
*EXPERIMENTAL* extension 'flask-framework' enabled
Created 'sample-flask_ubuntu-22.04-amd64.charm'.
Charms packed:
    sample-flask_ubuntu-22.04-amd64.charm

ubuntu@charm-dev-vm:~/sample-flask/charm$ juju refresh sample-flask --path=./sample-flask_ubuntu-22.04-amd64.charm --resource flask-app-image=localhost:32000/sample-flask:database --resource statsd-prometheus-exporter-image=prom/statsd-exporter:v0.24.0
Added local charm "sample-flask", revision 2, to the model
adding endpoint "postgresql" to default space "alpha"
no change to endpoints in space "alpha": grafana-dashboard, ingress, logging, metrics-endpoint, secret-storage

# The sample-flask charm status can be blocked with some warning messages, due to the database is not connected yet
ubuntu@charm-dev-vm:~/sample-flask/charm$ juju status
Model        Controller  Cloud/Region        Version  SLA          Timestamp
welcome-k8s  microk8s    microk8s/localhost  3.1.7    unsupported  08:12:42Z

App             Version  Status   Scale  Charm           Channel    Rev  Address         Exposed  Message
sample-flask             waiting      1  sample-flask                 2  10.152.183.175  no       waiting for units to settle down

Unit               Workload  Agent  Address      Ports  Message
sample-flask/0*    blocked   idle   10.1.30.210         Webserver configuration check failed, please review your charm configuration or database relation
```

The next step is to deploy the [`postgresql-k8s`](https://charmhub.io/postgresql-k8s) charm in our model and integrate the `postgresql-k8s` charm with the `sample-flask` charm to provide a postgresql database to the Flask application.
After two charms integrated, the error message should disappear and the `sample-flask` Flask application is up and providing the visitor statistic functionality.

```bash
# Deploy the postgresql-k8s charm in 14/stable channel, --trust is needed because postgresql-k8s charm needs to update some kubernetes resources
ubuntu@charm-dev-vm:~/sample-flask$ juju deploy postgresql-k8s --channel 14/stable --trust
Located charm "postgresql-k8s" in charm-hub, revision 177
Deploying "postgresql-k8s" from charm-hub charm "postgresql-k8s", revision 177 in channel 14/stable on ubuntu@22.04/stable

# Wait until he postgresql-k8s charm to appear active, it might takes a few minutes
ubuntu@charm-dev-vm:~/sample-flask$ juju status
Model        Controller  Cloud/Region        Version  SLA          Timestamp
welcome-k8s  microk8s    microk8s/localhost  3.1.7    unsupported  08:06:40Z

App             Version  Status  Scale  Charm           Channel    Rev  Address         Exposed  Message
postgresql-k8s  14.9     active      1  postgresql-k8s  14/stable  177  10.152.183.228  no
sample-flask             active      1  sample-flask                 2  10.152.183.175  no

Unit               Workload  Agent  Address      Ports  Message
postgresql-k8s/0*  active    idle   10.1.30.209
sample-flask/0*    blocked   idle   10.1.30.210         Webserver configuration check failed, please review your charm configuration or database relation

# Integrate the sample-flask charm and the postgresql-k8s charm
ubuntu@charm-dev-vm:~/sample-flask/charm$ juju relate sample-flask postgresql-k8s

# Wait until the sample-flask charm and the postgresql-k8s charm idle at active status again
ubuntu@charm-dev-vm:~/sample-flask/charm$ juju status
Model        Controller  Cloud/Region        Version  SLA          Timestamp
welcome-k8s  microk8s    microk8s/localhost  3.1.7    unsupported  10:00:13Z

App             Version  Status  Scale  Charm           Channel    Rev  Address         Exposed  Message
postgresql-k8s  14.9     active      1  postgresql-k8s  14/stable  177  10.152.183.228  no       Primary
sample-flask             active      1  sample-flask                 5  10.152.183.175  no

Unit               Workload  Agent  Address      Ports  Message
postgresql-k8s/0*  active    idle   10.1.30.209         Primary
sample-flask/0*    active    idle   10.1.30.210

# Access the sample-flask website with the new IP address (see juju status output above)
# The visitor counter goes up each time
ubuntu@charm-dev-vm:~/sample-flask/charm$ curl 10.1.30.210:8000
<h1 dir="auto">Hola</h1>
<small>Visitors: 1</small>
ubuntu@charm-dev-vm:~/sample-flask/charm$ curl 10.1.30.211:8000
<h1 dir="auto">Hola</h1>
<small>Visitors: 2</small>
```
