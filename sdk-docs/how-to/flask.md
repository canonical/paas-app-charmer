# Add an environment variable

A charm configuration can be added if you require environment variables, for
example, to pass a token for a service. For example, add the following
configuration in `charmcraft.yaml`:

```yaml
config:
  options:
    token:
      description: The token for the service.
      type: string
      required: true
```

PaaS App Charmer will map this as the `FLASK_TOKEN` environment variable. In
general, the environment variable name is `FLASK_<config option name>` where the
config option name will be converted to upper case. The configuration can be set
on the deployed charm using `juju config <app name> token=<token>`

# Database migration

If your app depends on a database it is common to run a database migration
script before app startup which, for example, creates or modifies tables. This
can be done by incuding the `migrate.sh` script in the root of your project. It
will be executed with the same environment variables and context as the flask
app.

If the migration script fails, the app won't be started and the app charm will
go into blocked state. The migration script will be run on every unit and it is
assumed that it is idempotent (can be run multiple times) and that it can be run
on multiple units at the same time without causing issues. This can be achieved
by, for example, locking any tables during the migration.

# Including extra files in the OCI image

The following files are included in the image by default from the root of the project:

- `app`
- `app.py`
- `migrate`
- `migrate.sh`
- `migrate.py`
- `static`
- `templates`

To change this, the following snippet needs to be added to the `rockfile.yaml`:

```yaml
parts:
    flask-framework/install-app:
    prime:
        - flask/app/.env
        - flask/app/app.py
        - flask/app/webapp
        - flask/app/templates
        - flask/app/static
```

Note the `flask/app/` prefix that is required followed by the relative path to
the project root.

# Including additional debs in the OCI image

If your app requires debs, for example to connect to a database, add the
following snipped to the `rockfile.yaml`:

```yaml
parts:
    flask-framework/dependencies:
      stage-packages:
        # list required packages or slices for your flask application below.
        - libpq-dev
```

Note the `flask/app/` prefix that is required followed by the relative path to
the project root.

# Update the OCI image

After making a change to your app;

1. make sure that any new files will be included in the new OCI image. See
  [Including extra files in the OCI image](#including-additional-debs-in-the-oci-image)
1. Run `rockcraft pack` to create the new OCI image
1. Run
  `skopeo --insecure-policy copy --dest-tls-verify=false oci-archive:<path to rock file> docker://localhost:32000/<rock name>:<rock version>`
  to upload the OCI image to the registry
1. Run
  `juju refresh <app name> --path=<relative path to .charm file> --resource flask-app-image=<localhost:32000/<rock name>:<rock version>>`
  to deploy the new OCI image

# Update the app charm

After making a change to your app charm such as adding a new integration;

1. If you have made any changes that need to be in the OCI image, see
  [Update the OCI image](#update-the-oci-image)
1. Run `charmcraft pack` to create the new charm
1. Run
  `juju refresh <app name> --path=<relative path to .charm file> --resource flask-app-image=<localhost:32000/<rock name>:<rock version>>`
  to deploy the new charm

If anything goes wrong, try running `charmcraft clean` before another
`charmcraft pack`.

