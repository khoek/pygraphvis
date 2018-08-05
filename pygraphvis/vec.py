import math
import operator

def add(a, b):
    return tuple(map(operator.add, a, b))

def sub(a, b):
    return tuple(map(operator.sub, a, b))

def mul(v, c):
    return tuple(float(x) * float(c) for x in v)

def norm(v):
    return math.sqrt(sum(x ** 2 for x in v))

def int_round(v):
    return tuple(int(x) for x in v)

def rotate2d(v, angle):
    l = norm(v)
    return (l * math.sin(angle), l * math.cos(angle))
