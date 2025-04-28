# -*- python-indent-offset: 2; fill-column: 65 -*-

# interface
class Differentiable:
  # returns outputs.
  def compute(self, *inputs): pass
  # can only be called after compute() is called.
  # returns deltas to outputs.
  def update(self, *deltas): pass

class Pipeline(Differentiable):
  def __init__(self, *diffables):
    assert all(isinstance(x, Differentiable) for x in diffables)
    self.pipeline = diffables

  def compute(self, *inputs):
    for x in self.pipeline:
      inputs = [x.compute(*inputs)]
    return inputs

  def update(self, *deltas):
    for x in self.pipeline:
      deltas = [x.update(*deltas)]
    return deltas

class Fork(Differentiable):
  # f --> g
  #  \
  #   --> h
  def __init__(self, f, g, h):
    self.f = f
    self.g = g
    self.h = h
  def compute(self, *inputs):
    intermediate = self.f.compute(*inputs)
    return (self.g.compute(intermediate), self.h.compute(intermediate))
  def update(self, *deltas):
    intermediate = self.f.update(*deltas)
    return (self.g.update(intermediate), self.h.update(intermediate))

class Parallel(Differentiable):
  def __init__(self, f, g):
    self.f = f
    self.g = g
  def compute(self, input1, input2):
    return (self.f.compute(input1), self.g.compute(input2))
  def update(self, delta1, delta2):
    return (self.f.update(delta1), self.g.compute(delta2))


# ---------- Filtering a log ----------
class FilterLog(Differentiable):
  def __init__(self, predicate):
    self.pred = predicate
  def compute(self, input_log):
    return [x for x in input_log if self.pred(x)]
  def update(self, new_entries):
    return [x for x in new_entries if self.pred(x)]

class Sum(Differentiable):
  def __init__(self): pass
  def compute(self, entries):
    self.entries = entries
    return sum(entries)
  def update(self, changes):
    diff = 0
    for (i, new_value) in changes:
      diff += new_value - self.entries[i]
      self.entries[i] = new_value
    return diff


class Log(Differentiable):
  def __init__(self): pass
  def compute(self, *inputs):
    self.log = [inputs]
    return inputs
  def update(self, *deltas):
    self.log.append(deltas)
    return deltas

class Log1(Differentiable):
  def __init__(self): pass
  def compute(self, input):
    self.log = [input]
    return input
  def update(self, delta):
    self.log.append(delta)
    return delta


class Graph(Differentiable):
  def __init__(self, graph):
    self.graph = graph
    # Topological/dataflow order on nodes (sources --> sinks).
    self.order = []

    visited = set()
    def visit(node):
      if node in visited: return
      visited.add(node)
      # self.order should omit nodes that we don't have a rule to
      # compute ("sources").
      if node not in self.graph: return
      _, *deps = self.graph[node]
      for x in deps: visit(x)
      self.order.append(node)

    for node in graph: visit(node)

  def compute(self, inputs):
    # `inputs` should map each source node to its input value.
    results = dict(inputs)
    for node in self.order:
      diffable, *deps = self.graph[node]
      results[node] = diffable.compute(*(results[d] for d in deps))
    return results

  # Exactly the same as `compute()` except we call `update()` on
  # the nodes instead.
  def update(self, deltas):
    results = dict(deltas)
    for node in self.order:
      diffable, *deps = self.graph[node]
      results[node] = diffable.update(*(results[d] for d in deps))
    return results


# ---------- EXAMPLE ----------
g = Graph({
  "a": (Log(), "x", "y", "z"),
  "y": (Log1(), "x"),
  "z": (Log1(), "q"),
})

# class DiffPusher:
#     def __init__(self, graph):
#         self.graph = graph
#         self.store = {}
#         # Find the reverse dependencies.
#         self.consumers = {}
#         for node, (_, *deps) in graph.items():
#             for d in deps:
#                 self.consumers.setdefault(d, set()).add(node)

#         # Should we immediately run all nodes with empty input??
#         # HMMMMMM.
#         # If we want everything to be up to date, YES.
#         # But what does it even mean to run a node when its input hasn't been set?
#         # Aughhhh.
#         # Maybe each node should come with an initial state & changelog?

#     def read(self, node):
#         return self.store[node]

#     def update(self, node, delta):
#         assert node not in self.graph.keys()
#         worklist = {c: [(node, delta)] for c in self.consumers.get(node, [])}
#         while worklist:
#             # Pick a node that has unprocessed incoming diffs.
#             node = next(iter(worklist))
#             diffs = worklist.pop(node)
            
