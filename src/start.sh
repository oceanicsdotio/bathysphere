#!/usr/bin/env bash
gunicorn bathysphere_graph:app --bind 0.0.0.0:5000