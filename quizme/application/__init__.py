"""Application layer — orchestration.

Imports ``quizme.domain`` and the port *protocols* in :mod:`quizme.application.ports`.
Never imports an adapter directly; the composition root (functions/, web/) wires
concrete adapters in.
"""
