"""Publish only exact, scanned consumer JUnit and safe provenance metadata."""

from .publish import main

if __name__ == "__main__":
    main(consumer=True)
