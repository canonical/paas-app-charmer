# Integrations

The flask charms produced by PaaS App Charmer support the following
integrations:

* Ingress: [k8s charm](https://charmhub.io/traefik-k8s)
* MySQL: [machine](https://charmhub.io/mysql) and
  [k8s](https://charmhub.io/mysql-k8s) charm
* PostgreSQL: [machine](https://charmhub.io/postgresql) and
  [k8s](https://charmhub.io/postgresql-k8s) charm
* MongoDB: [machine charm](https://charmhub.io/mongodb)
* COS: [Canonical Observability Stack](https://charmhub.io/cos-lite)
* Redis: [machine charm](https://charmhub.io/redis-k8s)

More details for the integrations are below.

## MySQL, PostgreSQL, MongoDB and Redis

To make use of either MySQL or PostgreSQL add one of the following snippets to
the `charmcraft.yaml` file:

```yaml
requires:
  mysql:
    interface: mysql_client
    limit: 1
```

```yaml
requires:
  postgresql:
    interface: postgresql_client
    limit: 1
```

```yaml
requires:
  mongodb:
    interface: mongodb_client
    limit: 1
```

```yaml
requires:
  redis:
    interface: redis
    limit: 1
```

After the integration has been established, the connection string will be
available under the `MYSQL_DB_CONNECT_STRING`, `POSTGRESQL_DB_CONNECT_STRING`,
`MONGODB_DB_CONNECT_STRING` or `REDIS_DB_CONNECT_STRING`, respectively.

