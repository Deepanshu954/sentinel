FROM golang:1.22-alpine AS builder
WORKDIR /app
COPY go.mod go.sum ./
RUN go mod download
COPY . .
RUN CGO_ENABLED=0 go build -o demo-backend .

FROM alpine:3.19
RUN apk add --no-cache ca-certificates
COPY --from=builder /app/demo-backend /usr/local/bin/demo-backend
EXPOSE 8081
CMD ["demo-backend"]
