import random
import math

from enum import Enum
from pygraphvis import *
from urllib.request import urlopen
from threading import *

SPAWN_DIST = 7
DO_RECONNECT_EDGES = False

class NodeState(Enum):
    UNFETCHED = 1
    FETCHING  = 2
    FETCHED   = 3

class NodePrivateData():
    state = NodeState.UNFETCHED
    unrevealed = None
    real_degree = 0
    manually_static = False

    def __init__(self):
        self.unrevealed = []

    def update(self, node):
        if self.state == NodeState.UNFETCHED:
            self.state = NodeState.FETCHING
            node.style.value.font_colour = (255, 255, 0)
            node.style.invalidate()

            crawler = Thread(target = crawl_page, args = (node, ))
            crawler.daemon = True
            crawler.start()
        elif self.state == NodeState.FETCHED:
            self.reveal_one(node)

    def reveal_one(self, node):
        if len(self.unrevealed) == 0:
            return

        child_name = self.unrevealed.pop()

        v.lock.acquire()

        child = None
        for n in v.graph.nodes:
            if n.style.value.name == child_name:
                child = n

                if not DO_RECONNECT_EDGES:
                    v.lock.release()
                    self.reveal_one(node)
                    return
                break
        if child == None:
            child = create_new_node(node.pos, child_name)

        if not child in node.adj:
            node.adj[child] = None
        if not node in child.adj:
            child.adj[node] = None

        v.lock.release()

# Called under v.lock()
def create_new_node(parent_pos, name, random_off = True):
    spawn_dist = SPAWN_DIST if random_off else 0
    angle = random.uniform(0, 2 * math.pi)
    pos = vec.add(parent_pos, vec.rotate2d((spawn_dist, 0), angle))
    n = Node(name = name, pos = pos, colour = (100, 100, 100))
    n.private = NodePrivateData()
    v.graph.nodes.add(n)
    return n

def set_node_style(node):
    score = float(node.private.real_degree) / highest_degree
    node.style.value.radius = int(20 * score + 8)

    if node.private.manually_static:
        colour = (0, 255, 0)
    else:
        colour = vec.int_round(vec.mul((score, 0, 1 - score), 255))
    node.style.value.colour = colour

def restyle_nodes():
    v.lock.acquire()
    for node in v.graph.nodes:
        if node.private.state == NodeState.FETCHED:
            set_node_style(node)
    v.lock.release()

BANNED_CHARS = [":", "#", "%"]
def find_wiki_links(page):
    pages = set()

    html = urlopen("http://en.wikipedia.org/wiki/" + page).read()
    for str in html.decode('utf-8').split("\""):
        if str.startswith("/wiki/") and not any([c in str for c in BANNED_CHARS]):
            pages.add(str[6:])

    return list(pages)

def crawl_page(node):
    links = find_wiki_links(node.style.value.name)

    node.style.value.font_colour = (255, 255, 255)
    node.style.invalidate()
    node.private.state = NodeState.FETCHED
    node.private.unrevealed = links
    node.private.real_degree = len(links)

    global highest_degree
    highest_degree = max(highest_degree, len(links))

    for i in range(0, 5):
        node.private.reveal_one(node)

    restyle_nodes()

def event_handler(e):
    if e.type == InputType.QUIT:
        v.stop()
    elif e.type == InputType.M_MOVE:
        return

    node = v.get_mousedover_node()
    if node == None:
        return

    if e.type == InputType.MB_RIGHT and e.state == MouseState.UP:
        node.private.update(node)
    elif e.type == InputType.MB_MIDDLE and e.state == MouseState.UP:
        node.private.manually_static = not node.private.manually_static
        node.static = node.private.manually_static
        set_node_style(node)

if __name__ == "__main__":
    highest_degree = 1
    v = vis.Visualiser(graphs.DynamicGraph(), size = (1200, 1000),
        event_handler = event_handler)

    root_name = input("Please enter the name of a Wikipedia page: ")
    create_new_node((0, 0), root_name, False)

    v.render_loop()
