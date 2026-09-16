-- Runs once, on first boot of the volume. The test suite needs its own database
-- so it can truncate freely without touching real data.
CREATE DATABASE enola_test;
\connect enola_test
CREATE EXTENSION IF NOT EXISTS vector;
\connect enola
CREATE EXTENSION IF NOT EXISTS vector;
