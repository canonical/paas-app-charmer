Imagine you have a Go application backed up by a database such as
PostgreSQL and need to deploy it. In a traditional setup, this can be
quite a challenge, but with Juju you’ll find yourself deploying,
configuring, scaling, integrating, monitoring, etc., your Go
application in no time. Let’s get started!

In this tutorial we will build a rock and Kubernetes charm for a Go
application using the charm SDK, so we can have a Go application up
and running with Juju in about 90 minutes.

[note type=information status]

:open_book: **rock** <br>An Ubuntu LTS-based OCI compatible container image designed to meet security, stability, and reliability requirements for cloud-native software.

:open_book: **charm** <br>

A package consisting of YAML files + Python code that will automate every aspect of an application's lifecycle so it can be easily orchestrated with Juju.

:open_book: **Juju** <br>An orchestration engine for software operators that enables the deployment, integration and lifecycle management of applications using charms.
[/note]

**What you’ll need:**

- A workstation, e.g., a laptop, with amd64 architecture which has sufficient resources to launch a virtual machine with 4 CPUs, 4 GB RAM, and a 50 GB disk
    - Note that a workstation with arm64 architecture can complete the majority of this tutorial.
- Familiarity with Linux

**What you’ll do:**

- [Set things up](#heading--set-things-up)
- [Create the Go application](#heading--create-the-go-application)
- [Run the Go application locally](#heading--run-the-go-application-locally)
- [Pack the Go application into a rock](#heading--pack-the-go-application-into-a-rock)
- [Create the charm](#heading--create-the-charm)
- [Deploy the Go application](#heading--deploy-the-go-application)
  - [Enable `juju config app-hello-world greeting=<greeting>`](#heading--enable-juju-config-app-hello-world-greetinggreeting)
- [Integrate with a database](#heading--integrate-with-a-database)
- [Expose the app using ingress](#heading--expose-the-app-using-ingress)
- [Clean up environment](#heading--clean-up-environment)

[note type=positive status="At any point, to give feedback or ask for help"]
Don't hesitate to get in touch on [Matrix](https://matrix.to/#/#12-factor-charms:ubuntu.com) or [Discourse](https://discourse.charmhub.io/) (or follow the "Help improve this document in the forum" on the bottom of this doc to comment directly on the doc).
[/note]


<a href="#heading--set-things-up"><h2 id="heading--set-things-up">Set things up</h2></a>

Install Multipass.

> See more: [Multipass | How to install Multipass](https://multipass.run/docs/install-multipass)

Use Multipass to launch an Ubuntu VM. 

<a href="#heading--fast-track"><h3 id="heading--fast-track">Fast track approach</h3></a>

To fast-track the setup, launch a VM with the name `charm-dev` using the charm-dev blueprint:

```bash
multipass launch --cpus 4 --disk 50G --memory 4G --name charm-dev charm-dev
```

[note type=information status]
This step may take a few minutes to complete (10-15 minutes).

This is because the command downloads, installs, (updates,) and configures a number of packages, and the speed will be affected by network bandwidth (not just your own, but also that of the package sources).

However, once it's done, you'll have everything you'll need.
[/note]

Once the VM is up, open a shell into it:

```bash
multipass shell charm-dev
```

MicroK8s ingress is required to expose the Go application. Enable using:

```bash
sudo microk8s enable ingress
```

> See more: [ingress^](https://microk8s.io/docs/ingress)

<a href="#heading--hands-on"><h3 id="heading--hands-on">Hands-on approach</h3></a>

For a more hands-on setup, use Multipass to launch an Ubuntu VM with the name `charm-dev` from the 22.04 blueprint:

```bash
multipass launch --cpus 4 --disk 50G --memory 4G --name charm-dev 22.04
```

Once the VM is up, open a shell into it:

```bash
multipass shell charm-dev
```

In order to create the rock, you'll need to install Rockcraft:

```bash
sudo snap install rockcraft --channel latest/edge --classic
```

`LXD` will be required for building the rock. Make sure it is installed and initialised:

```bash
sudo snap install lxd
lxd init --auto
```

In order to create the charm, you'll need to install Charmcraft:

```bash
sudo snap install charmcraft --channel latest/edge --classic
```

MicroK8s is required to deploy the Go application on Kubernetes. Install MicroK8s:

```bash
sudo snap install microk8s --channel 1.31-strict/stable
sudo adduser $USER snap_microk8s
newgrp snap_microk8s
```

Wait for MicroK8s to be ready using `sudo microk8s status --wait-ready`. Several MicroK8s add-ons are required for deployment. The MicroK8s registry is required to host the OCI image of the Go application and ingress is required to expose the Go application. Enable all using:

```bash
sudo microk8s enable hostpath-storage
sudo microk8s enable registry
sudo microk8s enable ingress
```

> See more: [ingress^](https://microk8s.io/docs/ingress)

Juju is required to deploy the Go application. Install Juju and bootstrap a development controller:

```bash
sudo snap install juju --channel 3.5/stable
mkdir -p ~/.local/share
juju bootstrap microk8s dev-controller
```

<a href="#heading--create-directory"><h3 id="heading--create-directory">Create the tutorial directory</h3></a>

[note type=information status]
This tutorial requires version `3.2.0` or later of Charmcraft. Check the version of Charmcraft using `charmcraft --version` If you have an older version of Charmcraft installed, use `sudo snap refresh charmcraft --channel latest/edge` to get the latest edge version of Charmcraft.
[/note]

[note type=information status]
This tutorial requires version `1.5.4` or later of Rockcratf. Check the version of Rockcraft using `rockcraft --version` If you have an older version of Rockcraft installed, use `sudo snap refresh rockcraft --channel latest/edge` to get the latest edge version of Rockcraft.
[/note]

Finally, create a new directory for this tutorial and go inside it:

```bash
mkdir go-hello-world
cd go-hello-world
```

<a href="#heading--create-the-go-application"><h2 id="heading--create-the-go-application">Create the Go application</h2></a>

Start by creating the "Hello, world" Go application that will be used for this tutorial.

Create a `main.go` file, copy the following text into it and then save it:

```go
package main

import (
	"fmt"
	"log"
	"net/http"
)

func helloWorldHandler(w http.ResponseWriter, req *http.Request) {
	log.Printf("new hello world request")
	fmt.Fprintf(w, "Hello, world!\n")
}

func main() {
	log.Printf("starting hello world application")
	http.HandleFunc("/", helloWorldHandler)
	http.ListenAndServe(":8080", nil)
}
```

Install `go` and initialise the Go module:
```bash
sudo snap install go --classic
go mod init go-hello-world
go mod tidy
```

<a href="#heading--run-the-go-application-locally"><h2 id="heading--run-the-go-application-locally">Run the Go application locally</h2></a>

Build the Go application so it can be run:

```bash
go build .
```

Now that we have a binary compiled, let's run the go application to verify that it works:

```bash
./go-hello-world
```

Test the Goapplication by using `curl` to send a request to the root endpoint. You may need a new terminal for this; if you are using Multipass use `multipass shell charm-dev` to get another terminal:

```bash
curl localhost:8080
```

The Go application should respond with `Hello, world!`. The Go application looks good, so we can stop for now using <kbd>Ctrl</kbd> + <kbd>c</kbd>.

<a href="#heading--pack-the-go-application-into-a-rock"><h2 id="heading--pack-the-go-application-into-a-rock">Pack the Go application into a rock</h2></a>

First, we'll need a `rockcraft.yaml` file. Rockcraft will automate its creation and tailoring for a Go application by using the `go-framework` profile:

```bash
rockcraft init --profile go-framework
```

The `rockcraft.yaml` file will automatically be created and set the
name based on your working directory. Open the file in a text editor
and check that the `name` is `go-hello-world`. Ensure that `platforms`
includes the architecture of your host. For example, if your host uses
the ARM architecture, include `arm64` in `platforms`.

[note type=information status]
For this tutorial, we'll use the `name` "go-hello-world" and assume you are on the `amd64` platform. Check the architecture of your system using `dpkg --print-architecture`. Choosing a different name or running on a different platform will influence the names of the files generated by Rockcraft.
[/note]

Pack the rock:

```bash
ROCKCRAFT_ENABLE_EXPERIMENTAL_EXTENSIONS=1 rockcraft pack
```

[note type=information status]
Depending on your system and network, this step can take a couple of minutes to finish.
[/note]

Once Rockcraft has finished packing the Go rock, you'll find a new file in your working directory with the `.rock` extension:

```bash
ls *.rock -l
```

[note type=information status]
If you changed the `name` or `version` in `rockcraft.yaml` or are not on an `amd64` platform, the name of the `.rock` file will be different for you.
[/note]

The rock needs to be copied to the Microk8s registry so that it can be deployed in the Kubernetes cluster:

```bash
rockcraft.skopeo --insecure-policy copy --dest-tls-verify=false oci-archive:go-hello-world_0.1_amd64.rock docker://localhost:32000/go-hello-world:0.1
```

> See more: [skopeo^](https://manpages.ubuntu.com/manpages/jammy/man1/skopeo.1.html)

<a href="#heading--create-the-charm"><h2 id="heading--create-the-charm">Create the charm</h2></a>

Create a new directory for the charm and go inside it:

```bash
mkdir charm
cd charm
```

We'll need a `charmcraft.yaml`, `requirements.txt` and source code for the charm. The source code contains the logic required to operate the Go application. Charmcraft will automate the creation of these files by using the `go-framework` profile:

```bash
charmcraft init --profile go-framework --name go-hello-world
```

The files will automatically be created in your working directory. 

The charm depends on several libraries. Download the libraries and pack the charm:

```bash
charmcraft fetch-libs
CHARMCRAFT_ENABLE_EXPERIMENTAL_EXTENSIONS=1 charmcraft pack
```

[note type=information status]
Depending on your system and network, this step can take a couple of minutes to finish.
[/note]

Once Charmcraft has finished packing the charm, you'll find a new file in your working directory with the `.charm` extension:

```bash
ls *.charm -l
```

[note type=information status]
If you changed the name in charmcraft.yaml or are not on the amd64 platform, the name of the `.charm` file will be different for you.
[/note]

<a href="#heading--deploy-the-go-application"><h2 id="heading--deploy-the-go-application">Deploy the Go application</h2></a>

A Juju model is needed to deploy the application. Let's create a new model:

```bash
juju add-model go-hello-world
```

[note type=information status]
If you are not on a host with the amd64 architecture, you will need to include a constraint to the Juju model to specify your architecture. For example, for the arm64 architecture, use `juju set-model-constraints -m go-hello-world arch=arm64`. Check the architecture of your system using `dpkg --print-architecture`.
[/note]

Now the Go application can be deployed using Juju:

```bash
juju deploy ./go-hello-world_amd64.charm go-hello-world --resource app-image=localhost:32000/go-hello-world:0.1
```

[note type=information status]
It will take a few minutes to deploy the Go application. You can monitor the progress using `juju status --watch 5s`. Once the status of the App has gone to `active`, you can stop watching using  <kbd>Ctrl</kbd> + <kbd>c</kbd>.

> See more: [Command 'juju status'](/t/10173)
[/note]

The Go application should now be running. We can monitor the status of the deployment using `juju status` which should be similar to the following output:

```
go-hello-world  microk8s    microk8s/localhost  3.5.4    unsupported  14:35:07+02:00

App             Version  Status  Scale  Charm           Channel  Rev  Address         Exposed  Message
go-hello-world           active      1  go-hello-world             0  10.152.183.229  no       

Unit               Workload  Agent  Address      Ports  Message
go-hello-world/0*  active    idle   10.1.157.79         
```

Test the deployment using `curl` to send a request to the root endpoint. The IP address is the Address listed in the Unit section of the `juju status` output (e.g., `10.1.157.79` in the sample output above):

```bash
$ curl 10.1.157.79:8080
Hello, world!
```

<a href="#heading--enable-juju-config-go-world-greetinggreeting"><h2 id="heading--enable-juju-config-go-hello-world-greetinggreeting">Configure the Go application</h2></a>

Now let's customise the greeting using a configuration option. We will expect this configuration option to be available in the Go app configuration under the keyword `GREETING`. Go back out to the root directory of the project using `cd ..` and copy the following code into `main.go`:

```python
package main

import (
	"fmt"
	"log"
	"os"
	"net/http"
)

func helloWorldHandler(w http.ResponseWriter, req *http.Request) {
	log.Printf("new hello world request")
	greeting, found := os.LookupEnv("APP_GREETING")
	if !found {
	  greeting = "Hello, world!"
	}
	fmt.Fprintf(w, "%s\n", greeting)
}

func main() {
	log.Printf("starting hello world application")
	http.HandleFunc("/", helloWorldHandler)
	http.ListenAndServe(":8080", nil)
}
```

Open `rockcraft.yaml` and update the version to `0.2`. Run `ROCKCRAFT_ENABLE_EXPERIMENTAL_EXTENSIONS=1 rockcraft pack` again, then upload the new OCI image to the MicroK8s registry:

```bash
rockcraft.skopeo --insecure-policy copy --dest-tls-verify=false oci-archive:go-hello-world_0.2_amd64.rock docker://localhost:32000/go-hello-world:0.2
```

Change back into the charm directory using `cd charm`. The `go-framework` Charmcraft extension supports adding configurations to `charmcraft.yaml` which will be passed as environment variables to the Go application. Add the following to the end of the `charmcraft.yaml` file:

```yaml
config:
  options:
    greeting:
      description: |
        The greeting to be returned by the Go application.
      default: "Hello, world!"
      type: string
```

[note type=information status]
Configuration options are automatically capitalised and `-` are replaced by `_`. A `APP_` prefix will also be added.
[/note]

Run `CHARMCRAFT_ENABLE_EXPERIMENTAL_EXTENSIONS=1 charmcraft pack` again. The deployment can now be refreshed to make use of the new code:

```bash
juju refresh go-hello-world --path=./go-hello-world_amd64.charm --resource app-image=localhost:32000/go-hello-world:0.2
```

Wait for `juju status` to show that the App is `active` again. Verify that the new configuration has been added using `juju config go-hello-world | grep -A 6 greeting:` which should show the configuration option.

[note type=information status]
The `grep` command extracts a portion of the configuration to make it easier to check whether the configuration option has been added.
[/note]

Get the updated IP address shown in the Unit section of `juju status`. Using `curl 10.1.157.81:8080` shows that the response is still `Hello, world!` as expected. The greeting can be changed using Juju:

```bash
juju config go-hello-world greeting='Hi!'
```

`curl 10.1.157.81:8080` now returns the updated `Hi!` greeting.

[note type=information status]
It might take a short time for the configuration to take effect.
[/note]

<a href="#heading--integrate-with-a-database"><h2 id="heading--integrate-with-a-database">Integrate with a database</h2></a>

Now let's keep track of how many visitors your application has received. This will require integration with a database to keep the visitor count. This will require a few changes:

* We will need to create a database migration that creates the `visitors` table
* We will need to keep track how many times the root endpoint has been called in the database
* We will need to add a new endpoint to retrieve the number of visitors from the database

The charm created by the `go-framework` extension will execute the `migrate.sh` script if it exists. This script should ensure that the database is initialised and ready to be used by the application. We will create a `migrate.sh` file containing this logic.

Go back out to the tutorial root directory using `cd ..`. Open the `migrate.sh` file using a text editor and paste the following code into it:

```bash
#!/bin/bash

PGPASSWORD="${POSTGRESQL_DB_PASSWORD}" psql -h "${POSTGRESQL_DB_HOSTNAME}" -U "${POSTGRESQL_DB_USERNAME}" "${POSTGRESQL_DB_NAME}" -c "CREATE TABLE IF NOT EXISTS visitors (timestamp TIMESTAMP NOT NULL, user_agent TEXT NOT NULL);"
```

[note type=information status]
The charm will pass the Database connection string in the `POSTGRESQL_DB_CONNECT_STRING` environment variable once postgres has been integrated with the charm.
[/note]

Change the permissions of the file `migrate.sh` so it is executable:
```bash
chmod u+x migrate.sh
```

For the migrations to work we need the `postgresql-client` package
installed in the rock. As by default the `go-framework` uses the base
base, we would also need to install a shell interpreter. Let's do it
as a slice, so it does not include unnecessary files. Add the
following to the end of the `rockcraft.yaml` file:
```yaml
parts:
  runtime-debs:
    plugin: nil
    stage-packages:
      # Added manually for the migrations
      - postgresql-client
  runtime-slices:
    plugin: nil
    stage-packages:
      # Added manually for the migrations
      - bash_bins
```

Open the `rockcraft.yaml` file in a text editor and update the version to `0.3`.

To be able to connect to postgresql from the Go app the library `pgx` will be used.
The app code needs to be updated to keep
track of the number of visitors and to include a new endpoint to
retrieve the number of visitors to the app. Open `main.go` in a text
editor and replace its contents with the following code:

```go
package main

import (
        "database/sql"
        "fmt"
        "log"
        "net/http"
        "os"
        "time"

        _ "github.com/jackc/pgx/v5/stdlib"
)

func helloWorldHandler(w http.ResponseWriter, req *http.Request) {
        log.Printf("new hello world request")
        postgresqlURL := os.Getenv("POSTGRESQL_DB_CONNECT_STRING")
        db, err := sql.Open("pgx", postgresqlURL)
        if err != nil {
                log.Printf("An error occurred while connecting to postgresql: %v", err)
                return
        }
        defer db.Close()

        ua := req.Header.Get("User-Agent")
        timestamp := time.Now()
        _, err = db.Exec("INSERT into visitors (timestamp, user_agent) VALUES ($1, $2)", timestamp, ua)
        if err != nil {
                log.Printf("An error occurred while executing query: %v", err)
                return
        }

        greeting, found := os.LookupEnv("APP_GREETING")
        if !found {
                greeting = "Hello, world!"
        }

        fmt.Fprintf(w, "%s\n", greeting)
}

func visitorsHandler(w http.ResponseWriter, req *http.Request) {
        log.Printf("visitors request")
        postgresqlURL := os.Getenv("POSTGRESQL_DB_CONNECT_STRING")
        db, err := sql.Open("pgx", postgresqlURL)
        if err != nil {
                return
        }
        defer db.Close()

        var numVisitors int
        err = db.QueryRow("SELECT count(*) from visitors").Scan(&numVisitors)
        if err != nil {
                log.Printf("An error occurred while executing query: %v", err)
                return
        }
        fmt.Fprintf(w, "Number of users in Postgresql %d\n", numVisitors)
}

func main() {
        log.Printf("starting hello world application")
        http.HandleFunc("/", helloWorldHandler)
        http.HandleFunc("/visitors", visitorsHandler)
        http.ListenAndServe(":8080", nil)
}
```

Checks all the packages in your project and their dependencies with the following command:
```bash
go mod tidy
```

Run `ROCKCRAFT_ENABLE_EXPERIMENTAL_EXTENSIONS=1 rockcraft pack` and upload the newly created rock to the MicroK8s registry:

```bash
rockcraft.skopeo --insecure-policy copy --dest-tls-verify=false oci-archive:go-hello-world_0.3_amd64.rock docker://localhost:32000/go-hello-world:0.3
```

Go back into the charm directory using `cd charm`. The Go app now requires a database which needs to be declared in the `charmcraft.yaml` file. Open `charmcraft.yaml` in a text editor and add the following section to the end:

```yaml
requires:
  postgresql:
    interface: postgresql_client
    optional: false
```

Pack the charm using `CHARMCRAFT_ENABLE_EXPERIMENTAL_EXTENSIONS=1 charmcraft pack` and refresh the deployment using Juju:

```bash
juju refresh go-hello-world --path=./go-hello-world_amd64.charm --resource app-image=localhost:32000/go-hello-world:0.3
```

Deploy `postgresql-k8s` using Juju and integrate it with `go-hello-world`:

```bash
juju deploy postgresql-k8s --trust
juju integrate go-hello-world postgresql-k8s
```

Wait for `juju status` to show that the App is `active` again. Get the updated IP address shown in the Unit section of `juju status`. `curl 10.1.87.215:8080` should still return the `Hi!` greeting. To check the total visitors, use `curl 10.1.87.215:8080/visitors` which should return `1` after the previous request to the root endpoint and should be incremented each time the root endpoint is requested. If we perform another request to `curl 10.1.87.215:8080`, `curl 10.1.87.215:8080/visitors` will return `2`.

<a href="#heading--expose-the-app-using-ingress"><h2 id="heading--expose-the-app-using-ingress">Expose the app using ingress</h2></a>

[note type=information status]
This step of the tutorial only works for hosts with the `amd64` architecture. For other architectures, skip this step.
[/note]

As a final step, let's expose the application using ingress. Deploy the `nginx-ingress-integrator` charm and integrate it with the Go app:

```bash
juju deploy nginx-ingress-integrator --trust
juju integrate nginx-ingress-integrator go-hello-world
```

The hostname of the app needs to be defined so that it is accessible via the ingress. We will also set the default route to be the root endpoint:

```bash
juju config nginx-ingress-integrator service-hostname=go-hello-world path-routes=/
```

[note type=information status]
By default, the port for the Go application should be 8080. If you want to change the default port, it can be done
with the configuration option `app-port` that will be exposed as `APP_PORT` to the Go application.
[/note]

Monitor `juju status` until everything has a status of `active`. Use `curl http://go-hello-world  --resolve go-hello-world:80:127.0.0.1` to send a request via the ingress. It should still be returning the `Hi!` greeting.

[note type=information status]
The `--resolve go-hello-world:80:127.0.0.1` option to the `curl` command is a way of resolving the hostname of the request without setting a DNS record.
[/note]

<a href="#heading--clean-up-environment"><h2 id="heading--clean-up-environment">Clean up environment</h2></a>

We've reached the end of this tutorial. We have created a Go application, deployed it locally, integrated it with a database and exposed it via ingress!

If you'd like to reset your working environment, you can run the following in the root directory for the tutorial:

```bash
# exit and delete the virtual environment
deactivate
rm -rf charm
# delete all the files created during the tutorial
rm go-hello-world_0.1_amd64.rock go-hello-world_0.2_amd64.rock go-hello-world_0.3_amd64.rock rockcraft.yaml main.go migrate.sh go-hello-world go.mod go.sum
# Remove the juju model
juju destroy-model go-hello-world --destroy-storage
```

If you created an instance using Multipass, you can also clean it up. Start by exiting it:

```bash
exit
```

And then you can proceed with its deletion:

```bash
multipass delete charm-dev
multipass purge
```


<a href="#heading--next-steps"><h2 id="heading--next-steps">Next steps</h2></a>

| If you are wondering...| visit...|
|---------------------------------|----------------------------------------------------|
| "How do I...?"                | [SDK How-to docs](/t/5521)            |
| "How do I debug?"     | [Charm debugging tools](/t/8047) |
| "What is...?"                  | [SDK Reference docs](/t/5522)       |
| "Why...?", "So what?" |  [SDK Explanation docs](/t/5523)   |

<br>

<small>**Contributors:** @econley, @jdkandersson , @tmihoc, @weii-wang  </small>

-------------------------
