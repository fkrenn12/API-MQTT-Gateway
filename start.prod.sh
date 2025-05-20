# /mariadb/certs/./generate_certificates.sh
docker compose  --env-file ./.env.prod -f docker-compose.prod.yml up -d
