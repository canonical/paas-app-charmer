// Copyright 2024 Canonical Ltd.
// See LICENSE file for licensing details.

package main

import (
	"context"
	"errors"
	"fmt"
	"go-app/internal/service"
	"io"
	"log"
	"os"
	"os/signal"
	"strings"
	"syscall"
	"time"

	"encoding/json"
	"net/http"

	_ "github.com/jackc/pgx/v5/stdlib"
	"github.com/prometheus/client_golang/prometheus"
	"github.com/prometheus/client_golang/prometheus/promhttp"
)

type mainHandler struct {
	counter prometheus.Counter
	service service.Service
}

func (h mainHandler) serveHelloWorld(w http.ResponseWriter, r *http.Request) {
	h.counter.Inc()
	log.Printf("Counter %#v\n", h.counter)
	fmt.Fprintf(w, "Hello, World!")
}

func (h mainHandler) serveEnvs(w http.ResponseWriter, r *http.Request) {
	h.counter.Inc()

	type EnvVar struct {
		Name, Value string
	}

	envVars := []EnvVar{}

	for _, e := range os.Environ() {
		pair := strings.SplitN(e, "=", 2)
		log.Printf("pair 1: %s pair2 %s\n", pair[0], pair[1])
		envVars = append(envVars, EnvVar{
			Name:  pair[0],
			Value: pair[1]})
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(envVars)
}

func (h mainHandler) servePostgresql(w http.ResponseWriter, r *http.Request) {
	err := h.service.CheckPostgresqlStatus()
	if err != nil {
		log.Printf(err.Error())
		io.WriteString(w, "FAILURE")
		return
	} else {
		io.WriteString(w, "SUCCESS")
	}
}

func main() {
	metricsPort, found := os.LookupEnv("APP_METRICS_PORT")
	if !found {
		metricsPort = "8000"
	}
	metricsPath, found := os.LookupEnv("APP_METRICS_PATH")
	if !found {
		metricsPath = "/metrics"
	}
	port, found := os.LookupEnv("APP_PORT")
	if !found {
		port = "8000"
	}

	// If wrong or missing, the sql check will fail.
	postgresqlUrl := os.Getenv("APP_POSTGRESQL_DB_CONNECT_STRING")

	requestCounter := prometheus.NewCounter(
		prometheus.CounterOpts{
			Name: "request_count",
			Help: "No of request handled",
		})

	mux := http.NewServeMux()
	mainHandler := mainHandler{
		counter: requestCounter,
		service: service.Service{PostgresqlUrl: postgresqlUrl},
	}
	mux.HandleFunc("/", mainHandler.serveHelloWorld)
	mux.HandleFunc("/env", mainHandler.serveEnvs)
	mux.HandleFunc("/postgresql/status", mainHandler.servePostgresql)

	if metricsPort != port {
		prometheus.MustRegister(requestCounter)

		prometheusMux := http.NewServeMux()
		prometheusMux.Handle(metricsPath, promhttp.Handler())
		prometheusServer := &http.Server{
			Addr:    ":" + metricsPort,
			Handler: prometheusMux,
		}
		go func() {
			if err := prometheusServer.ListenAndServe(); !errors.Is(err, http.ErrServerClosed) {
				log.Fatalf("Prometheus HTTP server error: %v", err)
			}
			log.Println("Prometheus HTTP Stopped serving new connections.")
		}()
	} else {
		mux.Handle("/metrics", promhttp.Handler())
	}

	server := &http.Server{
		Addr:    ":" + port,
		Handler: mux,
	}
	go func() {
		if err := server.ListenAndServe(); !errors.Is(err, http.ErrServerClosed) {
			log.Fatalf("HTTP server error: %v", err)
		}
		log.Println("Stopped serving new connections.")
	}()

	sigChan := make(chan os.Signal, 1)
	signal.Notify(sigChan, syscall.SIGINT, syscall.SIGTERM)
	<-sigChan

	shutdownCtx, shutdownRelease := context.WithTimeout(context.Background(), 10*time.Second)
	defer shutdownRelease()

	if err := server.Shutdown(shutdownCtx); err != nil {
		log.Fatalf("HTTP shutdown error: %v", err)
	}
	log.Println("Graceful shutdown complete.")
}
