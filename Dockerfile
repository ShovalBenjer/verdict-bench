# stage 1: build the UI
# Tags, not digests, by choice at this repo's scale: npm ci pins the JS tree
# via the lockfile and the engine is stdlib-only, so the images' drift
# surface is small. An archival artifact would pin @sha256 digests here.
FROM node:20-slim AS uibuild
WORKDIR /build
COPY ui/package*.json ui/
RUN cd ui && npm ci
COPY ui/ ui/
COPY state/ state/
RUN cd ui && npm run build

# stage 2: engine + static UI, stdlib-only python
FROM python:3.12-slim
WORKDIR /app
COPY engine/ engine/
COPY data/ data/
COPY docs/ docs/
COPY --from=uibuild /build/ui/dist ui/dist
EXPOSE 8080
# serves the benchmark UI; engine invocable via `docker exec ... python3 engine/runner.py`
CMD ["python3", "-m", "http.server", "8080", "--directory", "ui/dist"]
