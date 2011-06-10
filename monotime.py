#!/usr/bin/env python
# Based on code from: http://anacrolix.googlecode.com/hg/projects/pimu/monotime.py


from __future__ import division

__all__ = ["monotonic_time"]

import ctypes
import os
import sys
import time


LINUX_LIBRT = 'librt.so.1'


if sys.platform == "win32":
    #import ctypes.wintypes

    #if sys.getwindowsversion()[0] >= 6:
        #QueryUnbiasedInterruptTime = ctypes.windll.kernel32.QueryUnbiasedInterruptTime
        #QueryUnbiasedInterruptTime.restype = ctypes.wintypes.BOOL
        #def monotonic_time():
            #val = ctypes.c_ulonglong(0)
            #if QueryUnbiasedInterruptTime(ctypes.byref(val)) == 0:
                #errno_ = ctypes.get_errno()
                #raise OSError(errno_, os.strerror(errno_))
            #else:
                #return val.value / 10000000.0
    #else:
        #GetTickCount = ctypes.windll.kernel32.GetTickCount
        #GetTickCount.restype = ctypes.wintypes.DWORD

        #def monotonic_time():
            #return GetTickCount() / 1000

    # According to the python docs time.clock on Windows uses QueryPerformanceCounter
    # which should give us the best accuracy and precision
    def monotonic_time():
        return time.clock()
else:
    CLOCK_MONOTONIC = 1 # see <linux/time.h>
    CLOCK_MONOTONIC_RAW = 4 # see /usr/include/linux/time.h in Ubuntu
    class timespec(ctypes.Structure):
        _fields_ = [
            ('tv_sec', ctypes.c_long),
            ('tv_nsec', ctypes.c_long)
        ]
    librt = ctypes.CDLL(LINUX_LIBRT, use_errno=True)
    clock_gettime = librt.clock_gettime
    clock_gettime.argtypes = [ctypes.c_int, ctypes.POINTER(timespec)]
    clock_gettime.restype = ctypes.c_int
    g_timespec = timespec()
    def monotonic_time():
        if clock_gettime(CLOCK_MONOTONIC_RAW, ctypes.byref(g_timespec)) != 0:
            errno_ = ctypes.get_errno()
            raise OSError(errno_, os.strerror(errno_))
        return g_timespec.tv_sec + g_timespec.tv_nsec / 1e9


if __name__ == "__main__":
    import timeit

    while True:
        print timeit.default_timer(), monotonic_time()
