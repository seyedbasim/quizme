"""Domain layer — pure logic, no I/O, no cloud SDK (AD-11, AD-18).

Nothing in this package may import an adapter, a web framework, a database
driver, or an Azure SDK. It is the part of Quizme that would survive a move
back to a local deployment unchanged.
"""
