"""Adapters — concrete implementations of the ports in
:mod:`quizme.application.ports`.

Azure implementations are the v1 target (AD-13). The ``*_local`` / fallback
modules are AD-18 stubs kept so the local re-host is never designed out; they are
not wired into the Azure deployment.

Adapters translate vendor/SDK errors into
:class:`quizme.domain.errors.AdapterError` subclasses at the boundary.
"""
