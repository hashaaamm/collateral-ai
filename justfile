# Collateral AI — monorepo task runner (Django backend). `just` to list.
export COMPOSE_FILE := "docker-compose.local.yml"

default:
    @just --list

# Build all images
build:
    docker compose build

# Start the full local stack (django + postgres + frontend)
up:
    docker compose up -d --remove-orphans

down:
    docker compose down

logs service="":
    docker compose logs -f {{ service }}

# Run a Django manage.py command in the backend container
manage *args:
    docker compose run --rm django python manage.py {{ args }}

migrate:
    just manage migrate

makemigrations:
    just manage makemigrations

# Create an admin user (email login)
createsuperuser:
    just manage createsuperuser

# Regenerate the frontend's typed API client from the backend OpenAPI schema
gen-api:
    docker compose run --rm frontend pnpm gen:api

# Backend tests
test *args:
    docker compose run --rm django pytest {{ args }}

# Lint (pre-commit) — run inside backend/
lint:
    cd backend && pre-commit run --all-files
