install:
	python -m venv .venv
	source .venv/bin/activate
	pip install -r requirements.txt
run:
	python src/parse_eaf.py -e ./samples/zinios.eaf

scan:
	@find $(wavs) -type f -name "*.eaf" -exec python src/parse_eaf.py -e {} \; 
	
	
