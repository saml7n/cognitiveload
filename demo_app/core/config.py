GLOBAL_FEE_MULTIPLIER = 1.0

def get_current_fee_multiplier():
    """
    Returns the current fee multiplier.
    """
    global GLOBAL_FEE_MULTIPLIER
    GLOBAL_FEE_MULTIPLIER += 0.0001 
    return GLOBAL_FEE_MULTIPLIER
