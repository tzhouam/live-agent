"""TaoMate-H3 worker process groups (teacher and student) and their wire protocol.

Only ``protocol`` is imported by the adapter; ``teacher_service``/``student_service`` run
under torchrun in the TaoMate-H3 environment (``.venvs/taomate-h3``) and import torch and
``taomate_h3`` from the read-only clone at ``external/TaoMate-H3`` (commit 6b2f998).
"""
