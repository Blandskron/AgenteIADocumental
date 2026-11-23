# Blandskron Documental — Atajos operativos locales (EVO-013)
.PHONY: up up-ollama up-studio up-agents up-full down backup eval-rag check-compose

up:
	docker compose up -d --build

up-ollama:
	docker compose -f compose.yaml -f docker/compose/ollama.yml --profile local-llm up -d --build

up-studio:
	STUDIO_ENABLED=true docker compose -f compose.yaml -f docker/compose/studio.yml --profile studio up -d --build

up-agents:
	AGENTS_ENABLED=true STUDIO_ENABLED=true docker compose -f compose.yaml -f docker/compose/studio.yml -f docker/compose/agents.yml --profile studio --profile agents up -d --build

up-full:
	AGENTS_ENABLED=true CODE_MODE_ENABLED=true STUDIO_ENABLED=true docker compose -f compose.yaml -f docker/compose/ollama.yml -f docker/compose/studio.yml -f docker/compose/agents.yml -f docker/compose/code-mode.yml --profile local-llm --profile studio --profile agents --profile code-mode up -d --build

down:
	docker compose down

backup:
	sh scripts/database/tools/backup_postgres16.sh

eval-rag:
	python3 scripts/eval/run_eval_real.py

check-compose:
	docker compose --env-file .env.example -f docker/docker-compose.yml config --quiet
