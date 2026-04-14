import hashlib

def combine_signatures(partials):
    if len(partials) < 2:
        raise Exception("Need 2-of-3 quorum")

    return hashlib.sha256("".join(partials).encode()).hexdigest()
