.PHONY: up down backend frontend migrate

up:
	docker compose up --build

down:
	docker compose down

backend:
	cd backend && uvicorn app.main:app --reload --port 8000

frontend:
	cd frontend && npm run dev

migrate:
	cd backend && alembic upgrade head
