---
name: coordinator
description: Coordinates one bounded specialist task and returns the final answer.
delegates:
  - ./worker.agent.md
---

# Instructions

Ask `worker` to analyze the task, then use its result in your own final answer.
