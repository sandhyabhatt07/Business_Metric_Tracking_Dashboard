.PHONY: install data data-small test

install:
	pip install -r requirements.txt

data:
	python -m data_generator.generate --out data/raw

data-small:
	python -m data_generator.generate --out data/raw --accounts 500

test:
	python -m pytest -q
