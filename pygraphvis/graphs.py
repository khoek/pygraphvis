import math
import random
import pygraphvis.vec as vec

ATTRACTION = 75.0

REPULSION = 10000.0
MIN_CLOSENESS = 2.0

FRICTION = 0.00001

KICK_DIST = 0.01
KICK_SIZE = 1

class NodeStyle:
    name = None
    radius = 9

    colour = (50, 0, 200)
    font_colour = (255, 255, 255)

class RenderedNodeStyle:
    text = None

class CachedAttribute:
    value = None
    cache = None
    valid = False

    def __init__(self, value = None, cache = None, valid = False):
        self.value = value
        self.cache = cache
        self.valid = valid

    def validate(self):
        self.valid = True

    def invalidate(self):
        self.valid = False

class Node:
    style = None
    pos = (0.0, 0.0)
    vel = (0.0, 0.0)
    force = (0.0, 0.0)

    private = None

    mass = 1
    static = False

    adj = None

    def __init__(self, name = "", colour = (100, 100, 100), pos = (0.0, 0.0), vel = (0.0, 0.0), mass = 1, static = False):
        self.style = CachedAttribute(value = NodeStyle(), cache = RenderedNodeStyle())
        self.style.value.name = name
        self.style.value.colour = colour
        self.pos = pos
        self.vel = vel
        self.mass = mass
        self.static = static
        self.adj = set()

class DynamicGraph:
    nodes = None

    def __init__(self, nodes = set()):
        self.nodes = nodes

    def accelerate(self, n):
        force = (0.0, 0.0)

        # attraction
        for m in n.adj:
            if n == m:
                continue
            delta = vec.sub(n.pos, m.pos)
            force = vec.sub(force, vec.mul(delta, ATTRACTION))

        # repulsion
        for m in self.nodes:
            if n == m:
                continue
            delta = vec.sub(n.pos, m.pos)
            dist = vec.norm(delta)
            if dist <= KICK_DIST and id(n) < id(m):
                angle = random.uniform(0, 2 * math.pi)
                kick = vec.rotate2d((KICK_SIZE, 0), angle)
                n.vel = vec.add(n.vel, kick)
                m.vel = vec.sub(m.vel, kick)

            dist = max(dist, MIN_CLOSENESS)
            delta = vec.mul(delta, REPULSION / (dist ** 3))
            force = vec.add(force, delta)

        n.force = force

    def move(self, n, dt):
        if n.static:
            n.vel = (0.0, 0.0)
            return

        n.vel = vec.add(n.vel, vec.mul(n.force, dt / n.mass))
        n.vel = vec.mul(n.vel, math.pow(FRICTION, dt))
        n.pos = vec.add(n.pos, vec.mul(n.vel, dt))

    def tick(self, dt):
        for n in self.nodes:
            self.accelerate(n)
        for n in self.nodes:
            self.move(n, dt)
