import sys
import math
import time
import threading
from enum import Enum

# Supress dumping to stdout during init
real_stdout = sys.stdout
sys.stdout = None
import pygame
import pygame.freetype
import pygame.gfxdraw
from pygame.locals import *
sys.stdout = real_stdout

import pygraphvis.vec as vec
import pygraphvis.graphs as graph

ZOOM_FACTOR = 1.2

SYS_FONTS = "DejaVu Sans Mono,Inconsolata,Menlo,Monaco"

class InputType(Enum):
    QUIT      = 1
    MB_LEFT   = 2
    MB_RIGHT  = 3
    MB_MIDDLE = 4
    MB_SCROLL = 5
    M_MOVE    = 6

def fromCode(code):
    if code == 1:
        return InputType.MB_LEFT
    elif code == 2:
        return InputType.MB_MIDDLE
    elif code == 3:
        return InputType.MB_RIGHT
    elif code == 4 or code == 5:
        return InputType.MB_SCROLL
    else:
        return None

class MouseState(Enum):
    UP = 1
    DOWN = 2

class InputEvent():
    type = None
    state = None

    def __init__(self, type, state = None):
        self.type = type
        self.state = state

class Visualiser:
    graph = None
    font = None
    should_exit = False
    event_handler = None
    _size = None

    ft = None

    viewport = None
    screen = None
    lock = None

    hide_names = False
    mouse_down = False
    pan_grab_pos = None
    viewport_down_pos = None
    viewport_down_width = None

    selected_node = None
    selected_node_was_static = False

    def __init__(self, graph, size = (1000, 1000), scale = 0.1, title = "pygraphvis", framerate = 50, event_handler = None):
        self.graph = graph
        self._size = size
        self.ft = FramerateTracker(framerate)
        self.event_handler = event_handler

        self.lock = threading.Lock()
        self.viewport = Viewport(vec.mul(size, -0.5 * scale), scale)
        self.should_stop = False

        pygame.init()

        self.screen = pygame.display.set_mode(self._size, RESIZABLE)
        self.font = pygame.freetype.SysFont(SYS_FONTS, 16, bold=True)

        pygame.display.set_caption(title)

    def stop(self):
        self.should_stop = True

    def project(self, v):
        viewport_pos = vec.sub(v, self.viewport.pos)
        return vec.int_round(vec.mul(viewport_pos, 1.0 / self.viewport.scale))

    def unproject(self, v):
        viewport_pos = vec.mul(v, self.viewport.scale)
        return vec.add(viewport_pos, self.viewport.pos)

    def find_node_at(self, pos):
        self.lock.acquire()
        try:
            for n in self.graph.nodes:
                if vec.norm(vec.sub(n.pos, pos)) <= n.style.value.radius * self.viewport.scale:
                    return n
            return None
        finally:
            self.lock.release()

    def draw_node(self, n):
        screen_pos = self.project(n.pos)
        pygame.draw.circle(self.screen, n.style.value.colour, screen_pos, n.style.value.radius, 0)

        if not self.hide_names:
            if not n.style.valid:
                n.style.cache.text, bdrect = self.font.render(n.style.value.name, fgcolor=n.style.value.font_colour)
                n.style.validate()

            text = n.style.cache.text
            self.screen.blit(text, vec.add(screen_pos, (-0.5 * text.get_width(), text.get_height() - 7)))

    def draw_edge(self, n, m, thickness, colour):
        z1 = self.project(n.pos)
        z2 = self.project(m.pos)
        if thickness <= 1:
            pygame.draw.aaline(self.screen, colour, z1, z2, 1)
        else:
            angle = math.atan2(z2[1] - z1[1], z2[0] - z1[0])
            delta = vec.rotate2d((thickness / 2.0, 0), angle)
            delta = (-delta[0], delta[1])
            p1 = vec.add(z1, delta)
            p2 = vec.sub(z1, delta)
            p3 = vec.sub(z2, delta)
            p4 = vec.add(z2, delta)

            pygame.gfxdraw.aapolygon(self.screen, (p1, p2, p3, p4), colour)
            pygame.gfxdraw.filled_polygon(self.screen, (p1, p2, p3, p4), colour)

    def draw_bg(self):
        self.screen.fill((20, 20, 20))

    # Is the mouse over a node?
    def get_mousedover_node(self):
        return self.find_node_at(self.unproject(pygame.mouse.get_pos()))

    # Are we currently dragging a node?
    def get_selected_node(self):
        return self.selected_node

    def handle_input(self):
        for event in pygame.event.get():
            if event.type == QUIT:
                self.should_stop = False
                self.dispatch_event(InputEvent(InputType.QUIT))
            elif event.type == KEYDOWN:
                if event.key == K_h:
                    self.hide_names = not self.hide_names
            elif event.type == MOUSEBUTTONDOWN:
                if event.button in [1, 2, 3]:
                    self.mousebutton_pressed(event)
                    self.dispatch_event(InputEvent(fromCode(event.button), MouseState.DOWN))
                elif event.button == 4:
                    self.wheel_up(event)
                    self.dispatch_event(InputEvent(InputType.MB_SCROLL, MouseState.UP))
                elif event.button == 5:
                    self.wheel_down(event)
                    self.dispatch_event(InputEvent(InputType.MB_SCROLL, MouseState.DOWN))
            elif event.type == MOUSEBUTTONUP:
                if event.button == 1 or event.button == 3:
                    self.mousebutton_released(event)
                self.dispatch_event(InputEvent(fromCode(event.button), MouseState.UP))
            elif event.type == MOUSEMOTION:
                self.mouse_moved(event)
                self.dispatch_event(InputEvent(InputType.M_MOVE))
            elif event.type == pygame.VIDEORESIZE:
                self._size = (event.w, event.h)
                surface = pygame.display.set_mode(self._size, pygame.RESIZABLE)
        pygame.event.clear()

    def dispatch_event(self, e):
        if self.event_handler != None:
            self.event_handler(e)

    def mousebutton_pressed(self, event):
        real_pos = self.unproject(pygame.mouse.get_pos())
        n = self.find_node_at(real_pos)

        if event.button == 1:
            if self.mouse_down:
                return
            self.mouse_down = True
            self.pan_grab_pos = real_pos
            self.viewport_grab_pos = self.viewport.pos

            if n != None:
                self.selected_node_was_static = n.static
                n.static = True

            self.selected_node = n

    def mousebutton_released(self, event):
        if event.button == 1:
            if not self.mouse_down:
                return
            self.mouse_down = False

            if self.selected_node != None:
                self.selected_node.static = self.selected_node_was_static
                self.selected_node = None

    def mouse_moved(self, event):
        if not self.mouse_down:
            return

        mouse_pos = pygame.mouse.get_pos()
        if self.selected_node == None:
            mouse_pos = vec.mul(mouse_pos, self.viewport.scale)
            self.viewport.pos = vec.sub(self.pan_grab_pos, mouse_pos)
        else:
            self.selected_node.pos = self.unproject(mouse_pos)

    def scale_viewport(self, k, relative):
        delta = vec.mul(relative, self.viewport.scale)
        self.viewport.pos = vec.add(self.viewport.pos, vec.mul(delta, 1 - k))
        self.viewport.scale *= k

    def wheel_down(self, event):
        self.scale_viewport(1.0 / ZOOM_FACTOR, pygame.mouse.get_pos())

    def wheel_up(self, event):
        self.scale_viewport(ZOOM_FACTOR, pygame.mouse.get_pos())

    def get_viewport_dims(self):
        return vec.mul(self._size, self.viewport.scale)

    def in_viewport(self, n):
        p1 = self.viewport.pos
        p2 = vec.add(self.viewport.pos, self.get_viewport_dims())
        scale = self.viewport.scale
        xrect = n.style.value.radius * scale
        yrect = n.style.value.radius * scale
        return p1[0] <= n.pos[0] + xrect and p2[0] >= n.pos[0] - xrect and \
               p1[1] <= n.pos[1] + yrect and p2[1] >= n.pos[1] - yrect

    def crosses_viewport(self, n, m):
        return True

    def draw(self):
        self.draw_bg()

        self.lock.acquire()
        for n in self.graph.nodes:
            for m in n.adj:
                if self.crosses_viewport(n, m):
                    data = n.adj[m]
                    width, colour = (0.1, (255, 255, 255)) if data is None else data
                    self.draw_edge(n, m, width, colour)

        for n in self.graph.nodes:
            if self.in_viewport(n):
                self.draw_node(n)
        self.lock.release()

        pygame.display.flip()

    def render_loop(self):
        while not self.should_stop:
            self.ft.tick();
            self.handle_input()

            self.lock.acquire()
            self.graph.tick(1.0 / self.ft.actual_framerate)
            self.lock.release()

            self.draw()

class FramerateTracker:
    target_framerate = 0
    history_len = 0
    min_framerate = 0
    clock = pygame.time.Clock()

    actual_framerate = 0
    framerate_history = []

    def __init__(self, target_framerate, history_len = 5, min_framerate = 20):
        self.target_framerate = target_framerate
        self.actual_framerate = target_framerate
        self.history_len = history_len
        self.min_framerate = min_framerate

    def tick(self):
        framerate = 1000.0 / self.clock.tick_busy_loop(self.target_framerate)
        if framerate <= self.min_framerate:
            framerate = self.min_framerate

        self.framerate_history = self.framerate_history[1:] + [framerate * 1.0]
        self.framerate_actual = sum(self.framerate_history) / self.history_len

class Viewport():
    pos = None
    scale = None

    def __init__(self, pos = (0,0), scale = 1.0):
        self.pos = pos
        self.scale = scale
