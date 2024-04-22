# Architecture

PaaS App Charmer supports multiple frameworks, including the Flask web framework
for Python. It consists of several components:

1. The `flask-framework` Rockcraft profile and extension
1. The `flask-framework` Charmcraft profile and extension
1. The `paas-app-charmer` Python package

The Rockcraft extension is responsible for creating an OCI image from your flask
application. You can read more about it in the
[Use the flask-framework extension](https://canonical-rockcraft.readthedocs-hosted.com/en/latest/how-to/rocks/use-flask-extension/)
tutorial. The OCI images produced by the extension are designed to work
standalone and are also well integrated with the rest of the PaaS App Charmer
tooling. The `flask-framework` profile is helpful to initialise new projects
using the extension.

The Charmcraft extension is responsible for generating the ops code required to
run your flask application. The `flask-framework` profile is helpful to
initialise new projects using the extension.

The `paas-app-charmer` Python package contains the ops code which is used by the
`flask-framework` Charmcraft extension to operate your flask app. The package is
also used for other frameworks and consists of components that are shared across
multiple frameworks as well as Flask specific ops code.
