FROM ghcr.io/astral-sh/uv:0.12.2@sha256:596e7ea716217d76ff7ddfb8695833f7cb2a8d6589af32114a1b4a95c081fd4d AS uv

FROM python:3.12-slim-bookworm@sha256:6e13e65c55e33adf203d77ee371cf8bf5d81bd4902ef07565721f46bf44917af AS builder

COPY --from=uv /uv /usr/local/bin/uv
WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

COPY pyproject.toml uv.lock README.md ./
COPY src ./src
RUN uv sync --frozen --no-dev --no-editable

FROM python:3.12-slim-bookworm@sha256:6e13e65c55e33adf203d77ee371cf8bf5d81bd4902ef07565721f46bf44917af AS runtime

RUN groupadd --gid 65532 opspilot \
    && useradd --uid 65532 --gid 65532 --no-create-home --shell /usr/sbin/nologin opspilot

WORKDIR /app
COPY --from=builder --chown=65532:65532 /app/.venv /app/.venv

ENV PATH="/app/.venv/bin:${PATH}" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080

USER 65532:65532
EXPOSE 8080
ENTRYPOINT ["opspilot"]
CMD ["demo", "serve"]
