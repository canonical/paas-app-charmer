# PaaS App Charmer

Easily deploy and operate your Flask or Django applications and associated infrastructure,
such as databases and ingress, using open source tooling. This lets you focus on
creating applications for your users backed with the confidence that your
operations are taken care of by world class tooling developed by Canonical, the
creators of Ubuntu.

Have you ever created an application and then wanted to deploy it for your users
only to either be forced to use a proprietary public cloud platform or manage
the deployment and operations yourself? PaaS App Charmer will take your
application and create an OCI image using Rockcraft and operations code using
Charmcraft for you. The full suite of tools is open source so you can see
exactly how it works and even contribute! After creating the app charm and
image, you can then deploy your application into any Kubernetes cluster using
Juju. Need a database? Using Juju you can deploy a range of popular open source
databases, such as [PostgreSQL](https://charmhub.io/postgresql) or
[MySQL](https://charmhub.io/mysql), and integrate them with your application
with a few commands. Need an ingress to serve traffic? Use Juju to deploy and
integrate a range of ingresses, such as
[Traefik](https://charmhub.io/traefik-k8s), and expose your application to
external traffic in seconds.
