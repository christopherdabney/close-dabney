.PHONY: setup clean run-local run-docker

setup:
	python3 -m venv venv
	. venv/bin/activate && pip install -r requirements.txt

clean:
	rm -rf venv
	docker-compose down --volumes

run-local:
	. venv/bin/activate && python -m app.app

run-docker:
	docker-compose up --build