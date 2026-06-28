FROM python:3.12-slim

WORKDIR /app
COPY pyproject.toml ./
COPY src/ ./src/
COPY tests/ ./tests/
COPY evals/ ./evals/
COPY examples/ ./examples/
COPY fixtures/ ./fixtures/
COPY prompts/ ./prompts/
COPY README.md LICENSE ./

RUN pip install --no-cache-dir -e . pytest

CMD ["email-triage", "demo"]
