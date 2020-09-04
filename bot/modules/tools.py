import modules.config as cfg


def isAlNum(string):
    """ Little utility to check if a string contains only letters and numbers (a-z,A-Z,0-9)
        Parameters
        ----------
        string : str
            The string to be processed

        Returns
        -------
        isAlphaNum : boolean
            Result
    """
    for i in string.lower():
        cond = ord(i) >= ord('a') and ord(i) <= ord('z')
        cond = cond or (ord(i) >= ord('0') and ord(i) <= ord('9'))
        if not cond:
            return False
    return True
