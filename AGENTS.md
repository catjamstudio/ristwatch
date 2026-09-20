# RISTWatch Development Guide

- Keep RISTWatch isolated from any MooRIST installation.
- Use development ports `18081/tcp` and `5100/udp` unless explicitly changed.
- Store runtime state under `/config`; never commit secrets or production configuration.
- Keep telemetry parsing independent from subprocess management and covered by unit tests.
- Run backend tests, the frontend build, and the Docker build before releases.

