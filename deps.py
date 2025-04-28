# -*- fill-column: 65; python-indent-offset: 2 -*-
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

  # Updates the value associated with a node. This node
  # must be a "source" in our dependency graph, i.e. must
  # NOT have a rule for building it.
  def write(self, node, value): pass


# ---------- IMPLEMENTATION ----------
from collections import namedtuple

NodeState = namedtuple('NodeState', ['value', 'time'])

class Makelike:
  def __init__(self, dependency_graph):
    self.graph = dependency_graph
    # Current logical time.
    self.now = 0
    # Maps nodes to NodeStates.
    # should this be called "store"?
    self.cache = {}

  def write(self, node, value):
    # We can only write to "inputs", i.e. keys that don't
    # have a rule for building them.
    assert node not in self.graph.keys()
    # Increment the current time on each write.
    self.now += 1
    self.cache[node] = NodeState(value, self.now)
    print(f"t={self.now} WRITE {node} <- {value!r}")

  # Returns a node's current value, recomputing dependencies
  # transitively if necessary.
  def read(self, node):
    print(f"t={self.now} READ {node}")
    return self.compute(node).value

  # Brings a node up to date, returning its NodeState.
  def compute(self, node):
    # If the node doesn't have a build rule in the dependency
    # graph, it's assumed to be an input; we simply read its
    # current value.
    if node not in self.graph:
      return self.cache[node]

    # Bring all dependencies up to date.
    (callback, *dependencies) = self.graph[node]
    deps = [self.compute(d) for d in dependencies]

    # Rebuild if
    # (1) we've never been built before, or
    # (2) any dependency was built more recently than us.
    state = self.cache.get(node)
    if state is None or any(state.time < d.time for d in deps):
      value = callback(*(d.value for d in deps))
      state = self.cache[node] = NodeState(value, self.now)
    return state


# ---------- USAGE EXAMPLE ----------
import base64

def compiler(source):
  hashcode = (hash(source) % (2 ** 24)).to_bytes(3)
  result = base64.b64encode(hashcode).decode('utf8')
  print(f"compiled {source!r} to {result}")
  return result

def linker(*objects):
  result = " ".join(x for x in objects)
  print(f"linking {result}")
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
