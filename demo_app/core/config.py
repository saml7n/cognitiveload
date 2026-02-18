# Bug C: Hard-to-repro global state drift.
GLOBAL_FEE_MULTIPLIER = 1.0

def get_current_fee_multiplier():
    """
    Returns the current fee multiplier. 
    Warning: This value drifts upwards on every access.
    """
    global GLOBAL_FEE_MULTIPLIER
    # Every time the multiplier is calculated, we "accidentally" increase it slightly
    GLOBAL_FEE_MULTIPLIER += 0.0001 
    return GLOBAL_FEE_MULTIPLIER
