"""Regulatory monitoring engine."""
import sys
if sys.platform == 'win32':
    # Honor the Windows trust store (including managed corporate certificates).
    # Certificate verification remains enabled.
    import truststore
    truststore.inject_into_ssl()
