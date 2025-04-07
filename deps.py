# -*- fill-column: 60 -*-
# 
# a simple dependency tracking system
# pull-based, like Make


# ---------- INTERFACE ----------
class MakelikeInterface:
    # A graph is a dictionary mapping keys to (callback,
    # dependencies...) tuples. `callback` takes one argument
    # per dependency and returns the computed value.
    #
    # For instance,
    #
    #   def compiler(source_file): ...
    #   def linker(*object_files): ...
    #
    #   graph = {
    #     "foo.o": (compiler, "foo.c"),
    #     "bar.o": (compiler, "bar.o"),
    #     "lib.a": (linker, "foo.o", "bar.o"),
    #   }
    #
    #   make = Makelike(graph)
    #
    def __init__(self, dependency_graph): pass

    # Returns a node's current value.
    def read(self, node): pass

    # Updates the value associated with a node. This node must be a "source" in
    # our dependency graph, i.e. must NOT have a rule for building it.
    def write(self, node, value): pass


# ---------- IMPLEMENTATION ----------
from dataclasses import dataclass

# The current state associated with a node in our dependency graph.
@dataclass
class State:
    # Current computed value.
    value: object
    # The version of this value. Increments every time it's recomputed.
    version: int
    # The versions of each dependency used to rebuild this value. The order
    # matches the order the dependencies are listed in the dependency graph.
    dep_versions: List[int]

class Makelike:
    def __init__(self, dependency_graph):
        self.graph = dependency_graph
        # Maps each node to its current State.
        self.states = {}

    def write(self, node, value):
        print(f"WRITE {node} <- {value!r}")
        # We can only write to "inputs", i.e. keys that *don't* have a rule for
        # building them.
        assert node not in self.graph.keys()
        state = self.states.get(node)
        version = state.version + 1 if state is not None else 0
        self.states[node] = State(value, version, [])

    # Returns a node's current value, recomputing dependencies transitively if
    # necessary.
    def read(self, node):
        print(f"READ {node}")
        return self.compute(node).value

    # Brings a node up to date & computes its State.
    def compute(self, node):
        # If the node doesn't have a build rule in the dependency graph, it's
        # assumed to be an input; we simply read its current value.
        if node not in self.graph:
            return self.states[node]

        (callback, *dependencies) = self.graph[node]

        # Bring all dependencies up to date.
        dep_states = [self.compute(k) for k in dependencies]

        # We rebuild if
        # (1) we've never built before, or
        # (2) any dependency is out of date.
        state = self.states.get(node)
        rebuild = state is None or any(
            s.version != v for (s,v) in zip(dep_states, state.dep_versions))

        if rebuild:
            value = callback(*(s.value for s in dep_states))
            version = state.version + 1 if state is not None else 0
            dep_versions = [s.version for s in dep_states]
            state = State(value, version, dep_versions)
            self.states[node] = state

        return state


# ---------- USAGE EXAMPLE ----------
import base64

def compiler(source):
    result = base64.b64encode(source.encode('utf8')).decode("utf8")
    print(f"compiled {source!r} to {result!r}")
    return result

def linker(*object_file_contents):
    result = " ".join(object_file_contents)
    print(f"linking {result!r}")
    return result

graph = {
    "foo.o": (compiler, "foo.c"),
    "bar.o": (compiler, "bar.c"),
    "baz.o": (compiler, "baz.c"),
    "lib.a": (linker, "foo.o", "bar.o", "baz.o"),
}

def test():
    make = Makelike(graph)

    # Write initial values to foo.c and bar.c
    make.write("foo.c", "initial foo.c")
    make.write("bar.c", "initial bar.c")
    make.write("baz.c", "initial baz.c")
    print()
    liba = make.read("lib.a")

    # Modify bar.c
    print()
    make.write("baz.c", "second baz.c")
    print()
    liba = make.read("lib.a")
