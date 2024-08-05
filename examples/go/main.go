// Copyright 2024 Canonical Ltd.
// See LICENSE file for licensing details.

package main

import (
	"context"
	"errors"
	"fmt"
	"log"
	"os"
	"os/signal"
	"strings"
	"syscall"
	"time"

	"encoding/json"
	"github.com/prometheus/client_golang/prometheus"
	"github.com/prometheus/client_golang/prometheus/promhttp"
	"net/http"
)

type mainHandler struct {
	counter prometheus.Counter
}

func (h mainHandler) serveHelloWorld(w http.ResponseWriter, r *http.Request) {
	h.counter.Inc()
	log.Println("root handler")
	log.Printf("Counter %#v\n", h.counter)

	fmt.Fprintf(w, "Hello, World!! Path: %s\n", r.URL.Path)
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

	requestCounter := prometheus.NewCounter(
		prometheus.CounterOpts{
			Name: "request_count",
			Help: "No of request handled",
		})

	mux := http.NewServeMux()
	mainHandler := mainHandler{
		counter: requestCounter,
	}
	mux.HandleFunc("/", mainHandler.serveHelloWorld)
	mux.HandleFunc("/env", mainHandler.serveEnvs)

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
