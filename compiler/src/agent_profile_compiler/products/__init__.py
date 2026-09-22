"""Product probes: run a product CLI headless against a scripted model endpoint.

Product CLIs call real model APIs. To make a probe deterministic and free, the
CLI is pointed at a local server that speaks the provider's wire protocol and
answers from a script that inspects each request. The server records every
request, so a probe can assert what actually reached the model: which system
prompt, which tools, which tool results.
"""
