.PHONY: run test install check

install:
	pip install -r requirements.txt

run:
	python run_pipeline.py

test:
	pytest tests/ -v

check:
	@echo "Checking config..."
	@python -c "from config import settings; print('* Config loaded OK')"
	@echo "Checking DuckDB..."
	@python -c "import duckdb; print('* DuckDB OK')"
	@echo "Checking S3 connection..."
	@python -c "\
import boto3; from config import settings; \
s3 = boto3.client('s3', aws_access_key_id=settings.aws_access_key_id, \
aws_secret_access_key=settings.aws_secret_access_key, region_name=settings.aws_region); \
s3.head_bucket(Bucket=settings.s3_bucket); print('* S3 bucket reachable')"
