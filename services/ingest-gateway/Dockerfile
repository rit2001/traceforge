FROM golang:1.26-alpine AS build
WORKDIR /src
COPY services/ingest-gateway/go.mod services/ingest-gateway/go.sum* ./
RUN go mod download
COPY services/ingest-gateway/ .
RUN CGO_ENABLED=0 GOOS=linux go build -trimpath -o /out/ingest-gateway ./cmd/ingest-gateway
FROM alpine:3.22
RUN adduser -D -u 10001 traceforge
COPY --from=build /out/ingest-gateway /usr/local/bin/ingest-gateway
COPY schemas/capture-event-v0.schema.json /schemas/capture-event-v0.schema.json
COPY schemas/capture-event-v0.3.schema.json /schemas/capture-event-v0.3.schema.json
USER traceforge
EXPOSE 8080
HEALTHCHECK --interval=10s --timeout=3s --retries=5 CMD wget -qO- http://127.0.0.1:8080/healthz || exit 1
ENTRYPOINT ["/usr/local/bin/ingest-gateway"]
