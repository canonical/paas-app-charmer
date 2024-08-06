package service

import (
	"database/sql"
	"log"
)

type Service struct {
	PostgresqlUrl string
}

func (s *Service) CheckPostgresqlStatus() (err error) {
	db, err := sql.Open("pgx", s.PostgresqlUrl)
	if err != nil {
		return
	}
	defer db.Close()

	var version string
	err = db.QueryRow("SELECT version()").Scan(&version)
	if err != nil {
		return
	}
	log.Printf("postgresql version %s.", version)

	var numUsers int
	err = db.QueryRow("SELECT count(*) from USERS").Scan(&numUsers)
	if err != nil {
		return
	}
	log.Printf("Number of users in Postgresql %d.", numUsers)

	return
}
