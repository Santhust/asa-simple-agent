# Ensures pytest inserts the repo root on sys.path so tests can
# `import asa` directly — no installed package, no ini files needed,
# keeping the learning stack stdlib-only.