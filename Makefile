.RECIPEPREFIX = >
.PHONY: dev demo test check test-docker install uninstall doctor lint

dev:
> ./scripts/dev/dev.sh

test:
> ./scripts/dev/test.sh

demo:
> ./scripts/dev/demo.sh

test-docker:
> docker compose -f tests/docker/compose.yml run --rm tests

lint:
> ruff check whasp tests examples
> ruff format --check whasp tests examples

check:
> python3 -m compileall -q whasp
> for f in whasp/web/*.js whasp/web/ui/*.js; do node --check $$f; done

install:
> bash ./scripts/install/install.sh

uninstall:
> bash ./scripts/install/uninstall.sh

doctor:
> ./scripts/maintenance/doctor.sh
