"""Entry point for the packaged app (see heurebleue.spec). With no arguments the
command line opens the window; `HeureBleue doctor`, `HeureBleue start` and the
other subcommands still work from a terminal."""
import sys

from heurebleue.__main__ import main

sys.exit(main())
