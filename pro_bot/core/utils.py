import time
from functools import wraps
def retry(times=3, delay=1.0, backoff=2.0):
    def deco(fn):
        @wraps(fn)
        def wrap(*args, **kwargs):
            t, d = times, delay
            while t>0:
                try: return fn(*args, **kwargs)
                except Exception:
                    t-=1
                    if t==0: raise
                    time.sleep(d); d*=backoff
        return wrap
    return deco
