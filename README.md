# PaaS App Charmer

Easily deploy and operate your flask applications and associated infrastructure,
such as databases and ingress, using open source tooling. This lets you focus on
creating applications for your users backed with the confidence that your
operations are taken care of by world class tooling developed by Canonical, the
creators of Ubuntu.

Have you ever created an application and then wanted to deploy it for your users
only to either be forced to use a proprietary public cloud platform or manage
the deployment and operations yourself? PAAS App Charmer will take your
application and create an OCI image using rockcraft and operations code using
charmcraft for you. The full suite of tools is open source so you can see
exactly how it works and even contribute! After creating the app charm and
image, you can then deploy your application into any kubernetes cluster using
juju. Need a database? Using juju you can deploy a range of popular open source
databases, such as [postgreSQL](https://charmhub.io/postgresql) or
[MySQL](https://charmhub.io/mysql), and integrate them with your application
with a few commands. Need an ingress to serve traffic? Use juju to deploy and
integrate a range of ingress, such as
[traefik](https://charmhub.io/traefik-k8s), and expose your application to
external traffic in seconds.
