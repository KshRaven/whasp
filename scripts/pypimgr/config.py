"""Project-specific settings for pypimgr in this repository."""

PROJECT_NAME = "whasp"
PYPI_PACKAGE_NAME = "whasp"
GIT_REMOTE = "origin"
TAG_PREFIX = "v"
RELEASE_COMMIT_TEMPLATE = "Release v{version}"

# Project-relative paths.
PROJECT_FILE = "pyproject.toml"
CHANGELOG_FILE = "CHANGELOG.md"
ENV_FILE = ".env.release"
COMMIT_MESSAGE_FILE = "commit.txt"
REQUIRED_FILES = (
    "README.md",
    "LICENSE",
    PROJECT_FILE,
    CHANGELOG_FILE,
    "MANIFEST.in",
    ".gitignore",
)
# Directory names omitted from the source staging copy and regexes checked against archive paths.
TOP_LEVEL_EXCLUDES = ("experimental", "contrib", "data")
EXTRA_FORBIDDEN_PATHS = (r"(^|/)experimental/", r"(^|/)data/")

# Whasp ships no desktop or mobile apps, so nothing here triggers an "apps" build. Every tagged release creates a
# GitHub release with the sdist and wheel and publishes to TestPyPI and PyPI (see .github/workflows/release.yml).
APP_PATHS = ()

# Extra files that repeat the version; pypimgr updates them with the version file on every release/bump/fix.
# Each entry is (project-relative path, regex with three groups: text before, the version, text after).
VERSION_TARGETS = ()

PYPI_JSON_URL = "https://pypi.org/pypi/{package}/json"

PROJECT_LINKS = {
    "Repository": "https://github.com/KshRaven/whasp",
    "Release workflow": "https://github.com/KshRaven/whasp/actions/workflows/release.yml",
    "PyPI": "https://pypi.org/project/whasp/",
    "TestPyPI": "https://test.pypi.org/project/whasp/",
    "PyPI publisher settings": "https://pypi.org/manage/project/whasp/settings/publishing/",
    "TestPyPI publisher settings": "https://test.pypi.org/manage/project/whasp/settings/publishing/",
}
