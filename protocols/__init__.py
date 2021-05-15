"""Protocol schemes package.

This package supports a high level interface to importation of support
for URL protocol schemes.

Exported functions:

protocol_access(url, mode, params, data=None)
        returns the protocol scheme object for the scheme specified in
        the URL.

protocol_joiner(scheme)
        return a function to implement relative URL joining according
        to the scheme; or None if no such function exist.

"""

# Need different code here for ni than for 1.5 packages
try:
    __ # This fails with 1.5 packages, succeeds when using ni
except NameError:
    # 1.5 packages
    from ProtocolAPI import protocol_access, protocol_joiner
else:
    # Backward compatible solution for ni
    import ProtocolAPI

    for name in ['protocol_access', 'protocol_joiner']:
        setattr(__, name, getattr(ProtocolAPI, name))
    __.__doc__ = __doc__
