class AdapterException(Exception):
    pass


class AuthenticationException(AdapterException):
    pass


class ServiceException(AdapterException):
    pass


class TimeoutException(AdapterException):
    pass