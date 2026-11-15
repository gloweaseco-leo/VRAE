"""Run only consumer integration cases; never repeat M1 acceptance cases."""

from .lab import main

if __name__ == "__main__":
    main(consumer=True)
