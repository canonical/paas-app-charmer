# PaaS App Charmer

With PaaS App Charmer you can easily deploy and operate your flask applications
and associated infrastructure, such as databases and ingress, using open source
tooling. This lets you focus on creating applications for your users backed with
the confidence that your operations are taken care of by world class tooling
developed by Canonical, the creators of Ubuntu.

PaaS App Charmer will create an OCI image for you using the `flask-framework`
Rockcraft extension and take care of the ops code using the `flask-framework`
Charmcraft extension. Once you have the OCI image and the charm with the
packaged ops code, you can then juju deploy your flask application and integrate
it with databases, ingress and observability.

## PaaS App CHarmer Documentation

<!-- The links below are empty as I'm not sure where the best place is to point
people -->

| | |
|--|--|
|  [Tutorials]()</br>  Get started - a hands-on introduction to using PaaS App Charmer for new users </br> |  [How-to guides]() </br> Step-by-step guides covering key operations and common tasks |
| [Reference]() </br> Technical information - specifications, APIs, architecture | [Explanation]() </br> Concepts - discussion and clarification of key topics  |

## Contributing to this documentation

Documentation is an important part of this project, and we take the same
open-source approach to the documentation as the code. As such, we welcome
community contributions, suggestions and constructive feedback on our
documentation. Our documentation is hosted on the
[Charmhub forum]() to enable easy collaboration. Please use the "Help us improve
this documentation" links on each documentation page to either directly change
something you see that's wrong, ask a question, or make a suggestion about a
potential change via the comments section.

If there's a particular area of documentation that you'd like to see that's
missing, please
[file a bug](https://github.com/canonical/paas-app-charmer/issues).

## Project and community

PaaS App Charmer is a member of the Ubuntu family. It's an open-source project
that warmly welcomes community projects, contributions, suggestions, fixes, and
constructive feedback.

- [Code of conduct](https://ubuntu.com/community/code-of-conduct)
- [Get support](https://discourse.charmhub.io/)
- [Join our online chat](https://matrix.to/#/#12-factor-charms:ubuntu.com)
- [Contribute](#contribute)

Thinking about using PaaS App Charmer for your next project?
[Get in touch](https://matrix.to/#/#12-factor-charms:ubuntu.com)!

## Contribute

Is there something missing from the PaaS App Charmer framework? PaaS App Charmer
welcomes contributions! This section covers how to add a new integration and a
new framework.

### Add an Integration

There are a few recommended steps to add a new integration which we'll go
through below.

1. Please write a proposal on the
  [charm topic on discourse](https://discourse.charmhub.io/c/charm/41). This
  should cover things like:
  * The integration you intend add
  * For each of the frameworks that PaaS App Charmer supports:
    - The commonly used package(s) to make use of the integration
    - The environment variables, configuration etc. that would be made available
      to the app
    - An example for how to use the integration within an app
  * The proposed implementation in `paas-app-charmer`. Take a look at
    [`charm.py`](paas_app_charmer/_gunicorn/charm.py) for `gunicorn` based
    frameworks for integration examples.
1. Update the [tutorials](docs/tutorials) with the appropriate `fetch-lib`
  command
1. Raise a pull request to this repository adding support for the integration.
1. Add a commented entry for `requires` to all the relevant Charmcraft
  [templates](https://github.com/canonical/charmcraft/tree/main/charmcraft/templates)
  for the new integration

### Add a Framework

There are a few recommended steps to add a new framework which we'll go through
below.

1. Please write a proposal on the
  [charm topic on discourse](https://discourse.charmhub.io/c/charm/41). This
  should cover things like:
  * The programming language and framework you are thinking of
  * Create an example `rockcraft.yaml` file and build a working OCI image. To
    see an example for `flask`, install the `latest/edge` version of `rockcraft`
    and run `rockcraft init --profile flask-framework` and run
    `rockcraft expand-extensions` and inspect the output.
  * Create an example `charmcraft.yaml` file and build a working charm. To see
    an example for `flask`, install the `latest/edge` version of Charmcraft
    and run `charmcraft init --profile flask-framework` and run
    `charmcraft expand-extensions` and inspect the output.
  * How the configuration options of the charm map to environment variables,
    configurations or another method of passing the information to the app
  * The requirements and conventions for how users need to configure their app
    to work with PaaS App Charmer
  * Which web server to use
1. Raise a pull request to [rockcraft](https://github.com/canonical/rockcraft)
  adding a new extension and profile for the framework. This is the flask
  [profile](https://github.com/canonical/rockcraft/blob/fdd2dee18c81b12f25e6624a5a48f9f1ac9fdb90/rockcraft/commands/init.py#L79)
  and
  [extension](https://github.com/canonical/rockcraft/blob/fdd2dee18c81b12f25e6624a5a48f9f1ac9fdb90/rockcraft/extensions/gunicorn.py#L176).
  The OCI image should work standalone, not just with the charm for the
  framework.
1. Raise a pull request to this repository adding a new parent class that can be
  used by the app charms. The following is the
  [example for flask](./paas_app_charmer/flask/charm.py).
1. Raise a pull request to
  [charmcraft](https://github.com/canonical/charmcraft) adding a new extension
  and profile for the framework. This is the flask
  [profile](https://github.com/canonical/charmcraft/tree/main/charmcraft/templates/init-flask-framework)
  and
  [extension](https://github.com/canonical/charmcraft/blob/b6baa10566e3f3933cbd42392a0fe62cc79d2b6b/charmcraft/extensions/gunicorn.py#L167).
1. Write a tutorial and reference documentation for the framework. As an
  example, this is the flask [tutorial](docs/tutorials/flask.md) and
  [reference](docs/reference/flask.md) documentation.
